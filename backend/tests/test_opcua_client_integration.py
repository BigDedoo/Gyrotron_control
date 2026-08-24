import asyncio
from pathlib import Path

import pytest

from app.models import ConnectionState, SignalQuality
from app.opcua.client import OPCUAConnectionError, ReadOnlyOPCUAClient
from app.opcua.node_map import LogicalSignal
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
