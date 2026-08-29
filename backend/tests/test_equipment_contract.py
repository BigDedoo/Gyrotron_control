import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.equipment import build_equipment_snapshot, equipment_snapshot_with_data_state
from app.core.config import get_settings
from app.core.system_status import get_system_status
from app.models import (
    AlarmSeverity,
    AppMode,
    ConnectionState,
    DataSource,
    DataState,
    InterpretedState,
    SignalQuality,
    SignalValue,
    StateSignalValue,
)
from app.opcua.monitor import OPCUAMonitor
from app.opcua.node_map import REQUIRED_SIGNALS, LogicalSignal, LogicalStateSignal
from app.simulation import simulation_snapshot
from tests.opcua_simulator import LocalOPCUASimulator, make_opcua_settings


TIMESTAMP = datetime(2026, 2, 3, 4, 5, 6, tzinfo=timezone.utc)


def _reading(
    value: float | None,
    unit: str,
    quality: SignalQuality = SignalQuality.GOOD,
) -> SignalValue:
    return SignalValue(
        value=value,
        unit=unit,
        quality=quality,
        source_timestamp=TIMESTAMP,
        observed_at=TIMESTAMP,
        mapped=True,
    )


def _state(
    signal: LogicalStateSignal,
    interpreted: InterpretedState,
    quality: SignalQuality = SignalQuality.GOOD,
    *,
    severity: AlarmSeverity | None = None,
) -> StateSignalValue:
    return StateSignalValue(
        logical_name=signal.value,
        display_name=signal.value,
        group="Test equipment",
        mapped=True,
        raw_value=True,
        interpreted_state=interpreted,
        quality=quality,
        source_timestamp=TIMESTAMP,
        observed_at=TIMESTAMP,
        source=DataSource.OPCUA,
        data_state=DataState.LIVE if quality == SignalQuality.GOOD else DataState.DEGRADED,
        severity=severity,
    )


def _build(readings=None, states=None):
    return build_equipment_snapshot(
        source=DataSource.OPCUA,
        timestamp=TIMESTAMP,
        sequence=7,
        data_state=DataState.LIVE,
        readings=readings or {},
        state_signals=states or {},
    )


def test_complete_simulation_equipment_snapshot_is_typed_and_has_expected_units():
    equipment = simulation_snapshot(elapsed=10, timestamp=TIMESTAMP).equipment

    assert equipment.timestamp == TIMESTAMP
    assert equipment.coverage.complete is True
    assert equipment.coverage.mapped == equipment.coverage.total
    assert equipment.cmps.current.unit == "A"
    assert equipment.cfps.power.unit == "W"
    assert equipment.ipps.voltage.unit == "V"
    assert equipment.ipps.current.unit == "A"
    assert equipment.hvps.ahvps.voltage.unit == "kV"
    assert equipment.hvps.chvps.voltage.unit == "kV"
    assert equipment.pulse_generator.pulse_length.unit == "ms"
    assert equipment.pulse_generator.pulse_period.unit == "s"
    assert equipment.ipps.voltage.observed_at == TIMESTAMP


def test_partial_opcua_snapshot_preserves_quality_and_never_infers_state():
    equipment = _build(
        readings={
            LogicalSignal.CMPS_CURRENT: _reading(8.4, "A"),
            LogicalSignal.CFPS_POWER: _reading(None, "W", SignalQuality.BAD),
            LogicalSignal.IPPS_VOLTAGE: _reading(4.5, "V", SignalQuality.UNCERTAIN),
        }
    )

    assert equipment.cmps.current.value == pytest.approx(8.4)
    assert equipment.cmps.current.quality == SignalQuality.GOOD
    assert equipment.cmps.state.interpreted_state == InterpretedState.UNKNOWN
    assert equipment.cmps.state.mapped is False
    assert equipment.cfps.power.quality == SignalQuality.BAD
    assert equipment.cfps.power.value is None
    assert equipment.ipps.voltage.quality == SignalQuality.UNCERTAIN
    assert equipment.ipps.current.mapped is False
    assert equipment.ipps.current.quality == SignalQuality.UNAVAILABLE
    assert "cmps.state" in equipment.coverage.missing
    assert "cfps.power" in equipment.coverage.unavailable
    assert "ipps.current" in equipment.coverage.missing


def test_arc_hvps_and_pulse_contracts_are_conservative_and_explicit():
    equipment = _build(
        readings={
            LogicalSignal.AHVPS_VOLTAGE: _reading(42.0, "kV"),
            LogicalSignal.CHVPS_VOLTAGE: _reading(18.0, "kV"),
            LogicalSignal.PULSE_LENGTH: _reading(2.5, "ms"),
            LogicalSignal.PULSE_PERIOD: _reading(1.0, "s"),
        },
        states={
            LogicalStateSignal.ARC_DETECTOR: _state(
                LogicalStateSignal.ARC_DETECTOR,
                InterpretedState.ACTIVE,
                severity=AlarmSeverity.CRITICAL,
            ),
            LogicalStateSignal.PULSE_GENERATOR_STATE: _state(
                LogicalStateSignal.PULSE_GENERATOR_STATE,
                InterpretedState.ON,
            ),
        },
    )

    assert equipment.arc_detector.state.interpreted_state == InterpretedState.ACTIVE
    assert equipment.arc_detector.severity == AlarmSeverity.CRITICAL
    assert equipment.hvps.ahvps.voltage.value == pytest.approx(42.0)
    assert equipment.hvps.ahvps.protection.interpreted_state == InterpretedState.UNKNOWN
    assert equipment.hvps.ahvps.interlock.mapped is False
    assert equipment.hvps.chvps.voltage.value == pytest.approx(18.0)
    assert equipment.hvps.chvps.protection.interpreted_state == InterpretedState.UNKNOWN
    assert equipment.pulse_generator.pulse_length.value == pytest.approx(2.5)
    assert equipment.pulse_generator.pulse_period.value == pytest.approx(1.0)
    assert "requested" not in equipment.model_dump_json()


def test_simulation_and_opcua_equipment_contracts_have_identical_structure():
    simulation = simulation_snapshot(elapsed=10, timestamp=TIMESTAMP).equipment
    opcua = _build()

    def shape(value):
        if isinstance(value, dict):
            return {key: shape(item) for key, item in value.items()}
        if isinstance(value, list):
            return []
        return "leaf"

    assert shape(simulation.model_dump()) == shape(opcua.model_dump())


def test_cached_opcua_readings_are_conservative_when_snapshot_is_not_live():
    live = _build(
        readings={LogicalSignal.CMPS_CURRENT: _reading(8.4, "A")},
        states={
            LogicalStateSignal.CMPS_STATE: _state(
                LogicalStateSignal.CMPS_STATE,
                InterpretedState.ON,
            )
        },
    )

    stale = equipment_snapshot_with_data_state(live, DataState.STALE)
    unavailable = equipment_snapshot_with_data_state(live, DataState.UNAVAILABLE)

    assert stale.cmps.current.value == pytest.approx(8.4)
    assert stale.cmps.current.quality == SignalQuality.UNCERTAIN
    assert stale.cmps.state.interpreted_state == InterpretedState.UNKNOWN
    assert stale.coverage.trustworthy == 0
    assert unavailable.cmps.current.value is None
    assert unavailable.cmps.current.quality == SignalQuality.UNAVAILABLE
    assert unavailable.cmps.current.source_timestamp is None
    assert unavailable.cmps.state.interpreted_state == InterpretedState.UNKNOWN
    assert unavailable.coverage.trustworthy == 0


def test_local_opcua_monitor_populates_representative_equipment_contract():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        monitor = OPCUAMonitor(
            make_opcua_settings(simulator.endpoint_url, Path(__file__)),
            simulator.node_map(),
        )
        try:
            await monitor.client.connect()
            await monitor._read_once()
            snapshot = monitor._snapshot
            assert snapshot is not None
            equipment = snapshot.equipment
            assert equipment.cmps.current.value == pytest.approx(8.4)
            assert equipment.cfps.power.value == pytest.approx(350.0)
            assert equipment.ipps.voltage.value == pytest.approx(4.5)
            assert equipment.ipps.current.value == pytest.approx(1.8)
            assert equipment.hvps.ahvps.voltage.value == pytest.approx(42.0)
            assert equipment.hvps.chvps.voltage.value == pytest.approx(18.0)
            assert equipment.pulse_generator.pulse_length.value == pytest.approx(2.5)
            assert equipment.pulse_generator.pulse_period.value == pytest.approx(1.0)
            assert equipment.arc_detector.state.mapped is True

            monitor._connection_state = ConnectionState.CONNECTED
            monitor._last_successful_read = datetime.now(timezone.utc)
            cached_view = monitor.view()

            class CachedMonitor:
                node_map = monitor.node_map
                view_calls = 0

                def view(self):
                    self.view_calls += 1
                    return cached_view

            cached_monitor = CachedMonitor()
            settings = get_settings().model_copy(
                update={"app_mode": AppMode.OPCUA_READONLY, "opcua": monitor.settings}
            )
            status = get_system_status(settings, cached_monitor)
            assert cached_monitor.view_calls == 1
            assert status.equipment.cmps.current.value == pytest.approx(8.4)
        finally:
            await monitor.client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


def test_local_opcua_partial_map_marks_missing_equipment_fields_unavailable():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        selected_telemetry = set(REQUIRED_SIGNALS) | {
            LogicalSignal.CMPS_CURRENT,
            LogicalSignal.IPPS_VOLTAGE,
        }
        node_map = simulator.node_map(
            telemetry_signals=selected_telemetry,
            state_signals={LogicalStateSignal.CMPS_STATE},
        )
        monitor = OPCUAMonitor(
            make_opcua_settings(simulator.endpoint_url, Path(__file__)),
            node_map,
        )
        try:
            settings = get_settings().model_copy(
                update={"app_mode": AppMode.OPCUA_READONLY, "opcua": monitor.settings}
            )
            before_first_read = get_system_status(settings, monitor)
            assert before_first_read.equipment.cmps.current.mapped is True
            assert before_first_read.equipment.cmps.current.quality == SignalQuality.UNAVAILABLE
            assert before_first_read.equipment.cfps.power.mapped is False
            assert before_first_read.equipment.cmps.state.mapped is True

            await monitor.client.connect()
            await monitor._read_once()
            snapshot = monitor._snapshot
            assert snapshot is not None
            equipment = snapshot.equipment
            assert equipment.cmps.current.value == pytest.approx(8.4)
            assert equipment.cmps.state.interpreted_state == InterpretedState.ON
            assert equipment.cfps.power.mapped is False
            assert equipment.cfps.power.quality == SignalQuality.UNAVAILABLE
            assert equipment.ipps.voltage.value == pytest.approx(4.5)
            assert equipment.ipps.state.interpreted_state == InterpretedState.UNKNOWN
            assert equipment.coverage.complete is False
            assert "cfps.power" in equipment.coverage.missing
        finally:
            await monitor.client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())
