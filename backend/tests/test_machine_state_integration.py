import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.config import AppSettings
from app.core.system_status import get_system_status
from app.models import (
    AlarmMonitoringState,
    AppMode,
    ComponentState,
    ConditionState,
    DataState,
    EquipmentId,
    OverallState,
    SignalQuality,
)
from app.opcua.monitor import OPCUAMonitor
from app.opcua.node_map import LogicalStateSignal
from tests.opcua_simulator import LocalOPCUASimulator, make_opcua_settings


async def _wait_until(predicate, *, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition was not reached before timeout")
        await asyncio.sleep(0.02)


def _app_settings(opcua) -> AppSettings:
    return AppSettings(
        app_mode=AppMode.OPCUA_READONLY,
        cors_origins=("http://localhost:5173",),
        ldap_server_host="ldap.invalid.test",
        ldap_domain="invalid.test",
        ldap_port=636,
        ldap_use_ssl=True,
        ldap_timeout_seconds=1,
        session_cookie_name="gyro_session",
        session_ttl_seconds=3600,
        session_cookie_secure=False,
        opcua=opcua,
    )


def test_authoritative_components_interlocks_alarms_and_fault_transition():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        monitor = OPCUAMonitor(settings, simulator.node_map())
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().data_state == DataState.LIVE)
            status = get_system_status(_app_settings(settings), monitor)
            assert status.cps.state == ComponentState.ON
            assert status.cps.ready == ConditionState.OK
            assert status.cps.rectifier == ComponentState.ON
            assert status.cps.converter == ComponentState.ON
            assert status.cps.protection == ConditionState.OK
            assert status.aps.state == ComponentState.ON
            assert status.aps.ready == ConditionState.OK
            assert all(item.state == ConditionState.OK for item in status.interlocks)
            assert status.alarms.monitoring_state == AlarmMonitoringState.NO_ACTIVE
            assert status.alarms.active == []
            assert status.coverage.complete
            assert status.overall_state == OverallState.NOMINAL
            cmps = next(
                item for item in status.interlocks if item.logical_name == "interlock.cmps"
            )
            overvoltage = next(
                item
                for item in status.alarms.signals
                if item.logical_name == "alarm.overvoltage"
            )
            assert cmps.signal.equipment == EquipmentId.CMPS
            assert overvoltage.equipment == EquipmentId.AHVPS

            first_sequence = monitor.view().snapshot.sequence
            await simulator.publish_state_for_test(LogicalStateSignal.POOR_VACUUM, True)
            await _wait_until(lambda: monitor.view().snapshot.sequence > first_sequence)
            status = get_system_status(_app_settings(settings), monitor)
            vacuum = next(
                item for item in status.interlocks if item.logical_name == "interlock.poor_vacuum"
            )
            assert vacuum.state == ConditionState.FAULT
            assert vacuum.signal.raw_value is True
            assert status.overall_state == OverallState.FAULT

            first_sequence = monitor.view().snapshot.sequence
            await simulator.publish_state_for_test(LogicalStateSignal.POOR_VACUUM, False)
            await _wait_until(lambda: monitor.view().snapshot.sequence > first_sequence)
            first_sequence = monitor.view().snapshot.sequence
            await simulator.publish_state_for_test(LogicalStateSignal.ARC_DETECTOR, True)
            await _wait_until(lambda: monitor.view().snapshot.sequence > first_sequence)
            status = get_system_status(_app_settings(settings), monitor)
            assert status.alarms.monitoring_state == AlarmMonitoringState.ACTIVE
            assert status.alarms.active[0].code == "alarm.arc_detector"
            assert status.alarms.active[0].severity.value == "critical"
            assert status.overall_state == OverallState.FAULT
        finally:
            await monitor.stop()
            await simulator.stop()

    asyncio.run(scenario())


def test_unavailable_alarm_source_never_reports_no_active_alarms():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        node_map = simulator.node_map(state_missing=LogicalStateSignal.TEMPERATURE)
        monitor = OPCUAMonitor(settings, node_map)
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().snapshot is not None)
            status = get_system_status(_app_settings(settings), monitor)
            assert status.coverage.mapped == status.coverage.total
            assert status.coverage.trustworthy == status.coverage.total - 1
            assert status.alarms.active == []
            assert status.alarms.monitoring_state == AlarmMonitoringState.INCOMPLETE
            temperature = next(
                signal
                for signal in status.alarms.signals
                if signal.logical_name == "alarm.temperature"
            )
            assert temperature.quality in {SignalQuality.BAD, SignalQuality.UNAVAILABLE}
            assert status.overall_state == OverallState.UNKNOWN
        finally:
            await monitor.stop()
            await simulator.stop()

    asyncio.run(scenario())


def test_one_unavailable_state_does_not_erase_unrelated_values_or_report_nominal():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        node_map = simulator.node_map(state_missing=LogicalStateSignal.CPS_CONVERTER)
        monitor = OPCUAMonitor(settings, node_map)
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().snapshot is not None)
            status = get_system_status(_app_settings(settings), monitor)
            assert status.cps.converter == ComponentState.UNKNOWN
            assert status.cps.signals["converter"].quality in {
                SignalQuality.BAD,
                SignalQuality.UNAVAILABLE,
            }
            assert status.aps.ready == ConditionState.OK
            assert status.interlocks[0].state == ConditionState.OK
            assert not status.coverage.complete
            assert status.overall_state == OverallState.UNKNOWN
        finally:
            await monitor.stop()
            await simulator.stop()

    asyncio.run(scenario())


def test_partial_alarm_mapping_never_reports_no_active_alarms():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        selected = set(LogicalStateSignal) - {LogicalStateSignal.TEMPERATURE}
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        monitor = OPCUAMonitor(settings, simulator.node_map(state_signals=selected))
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().snapshot is not None)
            status = get_system_status(_app_settings(settings), monitor)
            assert status.alarms.active == []
            assert status.alarms.state == ConditionState.UNKNOWN
            assert status.alarms.monitoring_state == AlarmMonitoringState.INCOMPLETE
            assert "alarm.temperature" in status.coverage.missing
            assert status.overall_state == OverallState.UNKNOWN
        finally:
            await monitor.stop()
            await simulator.stop()

    asyncio.run(scenario())


def test_observation_freshness_does_not_depend_on_static_source_timestamp():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        monitor = OPCUAMonitor(settings, simulator.node_map())
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().data_state == DataState.LIVE)
            snapshot = monitor.view().snapshot
            signal = snapshot.machine_state.signals[LogicalStateSignal.CPS_READY.value]
            snapshot.machine_state.signals[LogicalStateSignal.CPS_READY.value] = signal.model_copy(
                update={"source_timestamp": datetime(2000, 1, 1, tzinfo=timezone.utc)}
            )
            status = get_system_status(_app_settings(settings), monitor)
            assert status.cps.ready == ConditionState.OK
            assert status.cps.signals["ready"].observed_at is not None
            assert status.cps.signals["ready"].source_timestamp.year == 2000

            snapshot.machine_state.signals[LogicalStateSignal.CPS_READY.value] = signal.model_copy(
                update={"quality": SignalQuality.UNCERTAIN, "data_state": DataState.DEGRADED}
            )
            uncertain = get_system_status(_app_settings(settings), monitor)
            assert uncertain.cps.ready == ConditionState.UNKNOWN
            assert uncertain.overall_state == OverallState.UNKNOWN
        finally:
            await monitor.stop()
            await simulator.stop()

    asyncio.run(scenario())


def test_disconnect_removes_trusted_positive_state_then_reconnect_restores_it():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        replacement = None
        await simulator.start()
        settings = make_opcua_settings(simulator.endpoint_url, Path(__file__))
        monitor = OPCUAMonitor(settings, simulator.node_map())
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().data_state == DataState.LIVE)
            assert get_system_status(_app_settings(settings), monitor).cps.ready == ConditionState.OK
            await simulator.crash()
            await _wait_until(lambda: monitor.view().connection_state.value != "connected")
            await monitor.stop()
            monitor._last_successful_read = datetime.now(timezone.utc)
            stale = get_system_status(_app_settings(settings), monitor)
            assert stale.cps.ready == ConditionState.UNKNOWN
            assert stale.cps.signals["ready"].data_state == DataState.STALE
            assert stale.cps.signals["ready"].raw_value is True

            monitor._last_successful_read = datetime.now(timezone.utc) - timedelta(
                seconds=settings.stale_after_seconds + 0.1
            )
            unavailable = get_system_status(_app_settings(settings), monitor)
            assert unavailable.cps.ready == ConditionState.UNKNOWN
            assert unavailable.alarms.monitoring_state == AlarmMonitoringState.UNAVAILABLE

            replacement = LocalOPCUASimulator(port=simulator.port)
            await replacement.start()
            await monitor.start()
            await _wait_until(lambda: monitor.view().data_state == DataState.LIVE)
            recovered = get_system_status(_app_settings(settings), monitor)
            assert recovered.cps.ready == ConditionState.OK
            assert recovered.overall_state == OverallState.NOMINAL
        finally:
            await monitor.stop()
            await simulator.stop()
            if replacement is not None:
                await replacement.stop()

    asyncio.run(scenario())
