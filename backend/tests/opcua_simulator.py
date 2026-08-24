import asyncio
import socket
from datetime import datetime, timezone
from pathlib import Path

from asyncua import Server, ua

from app.core.config import OPCUASettings
from app.opcua.node_map import (
    LogicalSignal,
    LogicalStateSignal,
    NodeMap,
    StateSignalKind,
    state_signal_kind,
)


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

TEST_STATE_VALUES = {
    signal: False
    if state_signal_kind(signal) == StateSignalKind.ALARM
    or signal == LogicalStateSignal.POOR_VACUUM
    else True
    for signal in LogicalStateSignal
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
        self.state_node_ids: dict[LogicalStateSignal, str] = {}
        self.state_values = dict(TEST_STATE_VALUES)

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
        self.state_node_ids = {}
        self.state_values = dict(TEST_STATE_VALUES)
        for signal, value in TEST_STATE_VALUES.items():
            node_id = ua.NodeId(f"TestGyrotron.State.{signal.value}", namespace)
            await gyrotron.add_variable(node_id, signal.value, value)
            server.iserver.aspace.set_attribute_value_callback(
                node_id,
                ua.AttributeIds.Value,
                lambda _node_id, _attribute, signal=signal: self._state_data_value(signal),
            )
            self.state_node_ids[signal] = node_id.to_string()
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
        state_signals: set[LogicalStateSignal] | None = None,
        state_missing: LogicalStateSignal | None = None,
        state_unavailable: LogicalStateSignal | None = None,
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
        selected_states = set(LogicalStateSignal) if state_signals is None else state_signals
        state_mappings = []
        for signal in LogicalStateSignal:
            if signal not in selected_states:
                continue
            node_id = self.state_node_ids[signal]
            if signal == state_missing:
                node_id += ".Missing"
            if signal == state_unavailable:
                node_id = "ns=invalid;s=Unparseable.State"
            if state_signal_kind(signal) == StateSignalKind.ALARM:
                interpretation = {"true": "active", "false": "inactive"}
                severity = "critical" if signal == LogicalStateSignal.ARC_DETECTOR else "warning"
            elif signal.value.endswith((".state", ".rectifier", ".converter")):
                interpretation = {"true": "on", "false": "off"}
                severity = None
            elif signal == LogicalStateSignal.POOR_VACUUM:
                interpretation = {"true": "fault", "false": "ok"}
                severity = None
            else:
                interpretation = {"true": "ok", "false": "fault"}
                severity = None
            state_mappings.append(
                {
                    "signal": signal,
                    "node_id": node_id,
                    "expected_type": "boolean",
                    "interpretation": interpretation,
                    "alarm_severity": severity,
                }
            )
        return NodeMap(
            schema_version=1,
            purpose="test",
            signals=mappings,
            state_signals=state_mappings,
        )

    def _state_data_value(self, signal: LogicalStateSignal) -> ua.DataValue:
        now = datetime.now(timezone.utc)
        return ua.DataValue(
            Value=ua.Variant(self.state_values[signal]),
            SourceTimestamp=now,
            ServerTimestamp=now,
        )

    async def publish_state_for_test(self, signal: LogicalStateSignal, value: bool) -> None:
        self.state_values[signal] = value
        await asyncio.sleep(0)


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
