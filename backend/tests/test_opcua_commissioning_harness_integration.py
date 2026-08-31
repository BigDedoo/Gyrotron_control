import asyncio
from pathlib import Path

import pytest

from app.models import ConnectionState, DataState, SignalQuality
from app.opcua.client import ReadOnlyOPCUAClient
from app.opcua.monitor import OPCUAMonitor
from app.opcua.node_map import LogicalSignal
from app.opcua.simulator import LocalOPCUASimulator, SimulatorScenario, make_opcua_settings


async def _wait_until(predicate, timeout: float = 5.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.05)
    raise AssertionError("condition not reached before timeout")


def test_full_good_contract_and_ipps_conversion():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator.commissioning()
        await simulator.start()
        client = ReadOnlyOPCUAClient(make_opcua_settings(simulator.endpoint_url, Path(__file__)))
        try:
            await client.connect()
            node_map = simulator.commissioning_node_map()
            readings = await client.read_signals(node_map.signals)
            states = await client.read_state_signals(node_map.state_signals)
            assert len(states) == 13
            assert readings[LogicalSignal.IPPS_VOLTAGE].value == 2500.0
            assert readings[LogicalSignal.IPPS_VOLTAGE].unit == "V"
            assert readings[LogicalSignal.IPPS_CURRENT].value == pytest.approx(0.003)
            assert readings[LogicalSignal.IPPS_CURRENT].unit == "A"
            assert all(value.quality == SignalQuality.GOOD for value in readings.values())
            assert all(value.quality == SignalQuality.GOOD for value in states.values())
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("simulator_scenario", "expected_quality", "expected_status"),
    [
        (SimulatorScenario.DEGRADED_QUALITY, SignalQuality.UNCERTAIN, "degraded"),
        (SimulatorScenario.BAD_QUALITY, SignalQuality.BAD, "bad_quality"),
        (SimulatorScenario.WRONG_DATATYPE, SignalQuality.BAD, "type_mismatch"),
        (SimulatorScenario.MISSING_NODE, SignalQuality.UNAVAILABLE, "unavailable"),
    ],
)
def test_targeted_fault_keeps_independent_signal_usable(simulator_scenario, expected_quality, expected_status):
    async def scenario() -> None:
        simulator = LocalOPCUASimulator.commissioning(simulator_scenario)
        await simulator.start()
        client = ReadOnlyOPCUAClient(make_opcua_settings(simulator.endpoint_url, Path(__file__)))
        try:
            await client.connect()
            readings = await client.read_signals(simulator.commissioning_node_map().signals)
            assert readings[LogicalSignal.IPPS_VOLTAGE].quality == expected_quality
            assert readings[LogicalSignal.IPPS_CURRENT].quality == SignalQuality.GOOD
            diagnostic = client.diagnostics_snapshot()[LogicalSignal.IPPS_VOLTAGE.value]
            if expected_status == "type_mismatch":
                assert diagnostic.observed_datatype == "String"
                assert "Datatype" in (diagnostic.last_error or "")
            elif expected_status == "bad_quality":
                assert diagnostic.raw_value == 2.5
            assert client.connected
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_values_are_rejected_by_local_opcua_reader(invalid: float):
    async def scenario() -> None:
        simulator = LocalOPCUASimulator(telemetry_values={LogicalSignal.ION_V: invalid})
        await simulator.start()
        client = ReadOnlyOPCUAClient(make_opcua_settings(simulator.endpoint_url, Path(__file__)))
        try:
            await client.connect()
            values = await client.read_signals(simulator.node_map().signals)
            assert values[LogicalSignal.ION_V].value is None
            assert values[LogicalSignal.ION_V].quality == SignalQuality.BAD
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


def test_stale_source_timestamp_is_distinct_and_diagnosable():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator.commissioning(SimulatorScenario.STALE_TIMESTAMP)
        await simulator.start()
        monitor = OPCUAMonitor(
            make_opcua_settings(simulator.endpoint_url, Path(__file__)),
            simulator.commissioning_node_map(),
        )
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().snapshot is not None)
            assert monitor.view().connection_state == ConnectionState.CONNECTED
            assert monitor.view().data_state == DataState.STALE
            row = next(
                row for row in monitor.diagnostics().signals
                if row.logical_field == LogicalSignal.IPPS_VOLTAGE.value
            )
            assert row.quality == SignalQuality.GOOD
            assert row.source_timestamp is not None
            assert row.backend_observed_at is not None
            assert row.age_seconds is not None and row.age_seconds > 500
            assert row.mapping_status == "stale"
        finally:
            await monitor.stop()
            await simulator.stop()

    asyncio.run(scenario())


def test_disconnect_reconnect_recovers_without_backend_restart():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator.commissioning(SimulatorScenario.DISCONNECT_RECONNECT)
        await simulator.start()
        monitor = OPCUAMonitor(
            make_opcua_settings(simulator.endpoint_url, Path(__file__)),
            simulator.commissioning_node_map(),
        )
        replacement = None
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().data_state == DataState.LIVE)
            await simulator.crash()
            await _wait_until(lambda: monitor.view().connection_state != ConnectionState.CONNECTED)
            replacement = LocalOPCUASimulator.commissioning(
                SimulatorScenario.DISCONNECT_RECONNECT,
                port=simulator.port,
            )
            await replacement.start()
            await _wait_until(lambda: monitor.view().data_state == DataState.LIVE)
            assert monitor.view().snapshot.equipment.ipps.voltage.value == 2500.0
        finally:
            await monitor.stop()
            await simulator.stop()
            if replacement is not None:
                await replacement.stop()

    asyncio.run(scenario())


def test_partial_map_is_explicit_and_has_no_missing_source_fakes():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator.commissioning(SimulatorScenario.PARTIAL_MAPPING)
        await simulator.start()
        monitor = OPCUAMonitor(
            make_opcua_settings(simulator.endpoint_url, Path(__file__)),
            simulator.commissioning_node_map(),
        )
        await monitor.start()
        try:
            await _wait_until(lambda: monitor.view().data_state == DataState.LIVE)
            equipment = monitor.view().snapshot.equipment
            assert equipment.ipps.voltage.value == 2500.0
            assert equipment.cmps.state.mapped is True
            assert equipment.cfps.state.mapped is False
            assert equipment.hvps.ahvps.voltage.mapped is False
            assert equipment.pulse_generator.pulse_length.mapped is False
        finally:
            await monitor.stop()
            await simulator.stop()

    asyncio.run(scenario())
