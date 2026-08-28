import asyncio
from pathlib import Path

import pytest

from app.models import ConnectionState, InterpretedState, SignalQuality
from app.opcua.client import OPCUAConnectionError, ReadOnlyOPCUAClient
from app.opcua.node_map import LogicalSignal, LogicalStateSignal, StateExpectedType
from tests.opcua_simulator import LocalOPCUASimulator, make_opcua_settings, unused_local_port


def test_client_connects_reads_typed_values_and_disconnects():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        client = ReadOnlyOPCUAClient(
            make_opcua_settings(simulator.endpoint_url, Path(__file__))
        )
        try:
            await client.connect()
            values = await client.read_signals(simulator.node_map().signals)
            assert client.connection_state == ConnectionState.CONNECTED
            assert values[LogicalSignal.ION_V].value == pytest.approx(4.5)
            assert values[LogicalSignal.ION_V].unit == "V"
            assert values[LogicalSignal.ION_V].quality == SignalQuality.GOOD
            assert values[LogicalSignal.ION_V].source_timestamp is not None
            assert len(values) == len(LogicalSignal)
        finally:
            await client.disconnect()
            await simulator.stop()
        assert client.connection_state == ConnectionState.DISCONNECTED

    asyncio.run(scenario())


def test_client_accepts_finite_integer_when_mapping_expects_integer():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator(integer_signal=LogicalSignal.ION_V)
        await simulator.start()
        client = ReadOnlyOPCUAClient(
            make_opcua_settings(simulator.endpoint_url, Path(__file__))
        )
        try:
            await client.connect()
            values = await client.read_signals(
                simulator.node_map(integer_type=LogicalSignal.ION_V).signals
            )
            sample = values[LogicalSignal.ION_V]
            assert sample.value == 4.0
            assert sample.quality == SignalQuality.GOOD
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "invalid",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_non_finite_opcua_numeric_values_are_bad_and_value_less(invalid: float):
    async def scenario() -> None:
        simulator = LocalOPCUASimulator(
            telemetry_values={LogicalSignal.ION_V: invalid}
        )
        await simulator.start()
        client = ReadOnlyOPCUAClient(
            make_opcua_settings(simulator.endpoint_url, Path(__file__))
        )
        try:
            await client.connect()
            values = await client.read_signals(simulator.node_map().signals)
            invalid_sample = values[LogicalSignal.ION_V]
            assert invalid_sample.value is None
            assert invalid_sample.quality == SignalQuality.BAD
            assert values[LogicalSignal.ION_I].quality == SignalQuality.GOOD
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


def test_non_finite_scaled_result_is_bad_and_value_less():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        client = ReadOnlyOPCUAClient(
            make_opcua_settings(simulator.endpoint_url, Path(__file__))
        )
        try:
            await client.connect()
            mapping = simulator.node_map().by_signal()[LogicalSignal.ION_V]
            mapping = mapping.__class__.model_validate(
                {**mapping.model_dump(mode="json"), "scale": 1e308}
            )
            sample = await client.read_signal(mapping)
            assert sample.value is None
            assert sample.quality == SignalQuality.BAD
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


def test_client_reports_unavailable_server_and_disconnects_cleanly():
    async def scenario() -> None:
        port = unused_local_port()
        client = ReadOnlyOPCUAClient(
            make_opcua_settings(
                f"opc.tcp://127.0.0.1:{port}/unavailable/",
                Path(__file__),
            )
        )
        with pytest.raises(OPCUAConnectionError):
            await client.connect()
        assert client.connection_state == ConnectionState.ERROR
        await client.disconnect()
        assert client.connection_state == ConnectionState.DISCONNECTED

    asyncio.run(scenario())


def test_missing_and_wrong_type_nodes_are_never_good():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator(integer_signal=LogicalSignal.HEAT_I)
        await simulator.start()
        client = ReadOnlyOPCUAClient(
            make_opcua_settings(simulator.endpoint_url, Path(__file__))
        )
        try:
            await client.connect()
            values = await client.read_signals(
                simulator.node_map(
                    missing=LogicalSignal.T_COLD,
                    unavailable=LogicalSignal.HE_LEVEL,
                    integer_type=LogicalSignal.ION_V,
                ).signals
            )
            assert values[LogicalSignal.T_COLD].quality in {
                SignalQuality.BAD,
                SignalQuality.UNAVAILABLE,
            }
            assert values[LogicalSignal.T_COLD].value is None
            assert values[LogicalSignal.ION_V].quality == SignalQuality.BAD
            assert values[LogicalSignal.ION_V].value is None
            assert values[LogicalSignal.HE_LEVEL].quality == SignalQuality.UNAVAILABLE
            assert values[LogicalSignal.HE_LEVEL].value is None
            assert values[LogicalSignal.HEAT_I].quality == SignalQuality.BAD
            assert values[LogicalSignal.HEAT_I].value is None
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


def test_client_preserves_raw_state_and_applies_only_configured_interpretation():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        client = ReadOnlyOPCUAClient(
            make_opcua_settings(simulator.endpoint_url, Path(__file__))
        )
        try:
            await client.connect()
            node_map = simulator.node_map(
                state_signals={
                    LogicalStateSignal.GS_DOORS,
                    LogicalStateSignal.POOR_VACUUM,
                }
            )
            values = await client.read_state_signals(node_map.state_signals)
            doors = values[LogicalStateSignal.GS_DOORS]
            vacuum = values[LogicalStateSignal.POOR_VACUUM]
            assert doors.raw_value is True
            assert doors.interpreted_state == InterpretedState.OK
            assert vacuum.raw_value is False
            assert vacuum.interpreted_state == InterpretedState.OK
            assert doors.source_timestamp is not None
            assert doors.observed_at is not None
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())


def test_wrong_type_and_unavailable_state_nodes_are_unknown_without_affecting_others():
    async def scenario() -> None:
        simulator = LocalOPCUASimulator()
        await simulator.start()
        client = ReadOnlyOPCUAClient(
            make_opcua_settings(simulator.endpoint_url, Path(__file__))
        )
        try:
            await client.connect()
            node_map = simulator.node_map(
                state_signals={LogicalStateSignal.GS_DOORS, LogicalStateSignal.WATERFLOW},
                state_missing=LogicalStateSignal.WATERFLOW,
            )
            wrong_type = node_map.state_signals[0].model_copy(
                update={"expected_type": StateExpectedType.INTEGER}
            )
            values = await client.read_state_signals(
                (wrong_type, node_map.state_signals[1])
            )
            assert values[wrong_type.signal].quality == SignalQuality.BAD
            assert values[wrong_type.signal].interpreted_state == InterpretedState.UNKNOWN
            unavailable = values[LogicalStateSignal.WATERFLOW]
            assert unavailable.quality in {SignalQuality.BAD, SignalQuality.UNAVAILABLE}
            assert unavailable.interpreted_state == InterpretedState.UNKNOWN
        finally:
            await client.disconnect()
            await simulator.stop()

    asyncio.run(scenario())
