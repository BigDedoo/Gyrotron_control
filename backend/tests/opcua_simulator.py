import asyncio
import socket
from pathlib import Path

from asyncua import Server, ua

from app.core.config import OPCUASettings
from app.opcua.node_map import LogicalSignal, NodeMap


TEST_VALUES = {
    LogicalSignal.ION_V: 4.5,
    LogicalSignal.ION_I: 1.8,
    LogicalSignal.HEAT_V: 7.0,
    LogicalSignal.HEAT_I: 3.2,
    LogicalSignal.HE_LEVEL: 68.0,
    LogicalSignal.T_HOT: 62.0,
    LogicalSignal.T_COLD: 28.0,
}

TEST_UNITS = {
    LogicalSignal.ION_V: "V",
    LogicalSignal.ION_I: "A",
    LogicalSignal.HEAT_V: "V",
    LogicalSignal.HEAT_I: "A",
    LogicalSignal.HE_LEVEL: "%",
    LogicalSignal.T_HOT: "degC",
    LogicalSignal.T_COLD: "degC",
}


def unused_local_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


class LocalOPCUASimulator:
    def __init__(
        self,
        port: int | None = None,
        *,
        integer_signal: LogicalSignal | None = None,
    ) -> None:
        self.port = port or unused_local_port()
        self.integer_signal = integer_signal
        self.endpoint_url = f"opc.tcp://127.0.0.1:{self.port}/gyrotron-test/"
        self.server: Server | None = None
        self.node_ids: dict[LogicalSignal, str] = {}

    async def start(self) -> None:
        server = Server()
        await server.init()
        server.set_endpoint(self.endpoint_url)
        namespace = await server.register_namespace("urn:gyrotron:test:readonly")
        gyrotron = await server.nodes.objects.add_object(namespace, "TestGyrotron")
        self.node_ids = {}
        for signal, value in TEST_VALUES.items():
            node_id = ua.NodeId(f"TestGyrotron.{signal.value}", namespace)
            server_value = int(value) if signal == self.integer_signal else value
            await gyrotron.add_variable(node_id, signal.value, server_value)
            self.node_ids[signal] = node_id.to_string()
        await server.start()
        self.server = server

    async def stop(self) -> None:
        server, self.server = self.server, None
        if server is not None:
            await server.stop()

    async def crash(self) -> None:
        """Abruptly drop test connections to exercise client recovery."""
        server, self.server = self.server, None
        if server is None:
            return
        binary_server = server.bserver
        if binary_server is not None and binary_server._server is not None:
            binary_server._server.close()
            await binary_server._server.wait_closed()
            for protocol in list(binary_server.clients):
                if protocol.transport is not None:
                    protocol.transport.abort()
            await asyncio.sleep(0)
        await asyncio.wait_for(server.stop(), timeout=2)

    def node_map(
        self,
        *,
        missing: LogicalSignal | None = None,
        unavailable: LogicalSignal | None = None,
        integer_type: LogicalSignal | None = None,
    ) -> NodeMap:
        mappings = []
        for signal in LogicalSignal:
            node_id = self.node_ids[signal]
            if signal == missing:
                node_id = node_id + ".Missing"
            if signal == unavailable:
                node_id = "ns=invalid;s=Unparseable"
            mappings.append(
                {
                    "signal": signal,
                    "node_id": node_id,
                    "expected_type": "integer" if signal == integer_type else "float",
                    "unit": TEST_UNITS[signal],
                }
            )
        return NodeMap(schema_version=1, purpose="test", signals=mappings)


def make_opcua_settings(endpoint_url: str, existing_path: Path) -> OPCUASettings:
    return OPCUASettings(
        endpoint_url=endpoint_url,
        connect_timeout_seconds=0.5,
        read_timeout_seconds=0.3,
        monitor_interval_seconds=0.05,
        reconnect_initial_seconds=0.05,
        reconnect_max_seconds=0.2,
        stale_after_seconds=0.5,
        node_map_path=existing_path,
        security_policy="None",
        security_mode="None",
    )
