from __future__ import annotations

import asyncio
import socket
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from asyncua import Server, ua
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.config import OPCUASettings
from app.opcua.node_map import (
    LogicalSignal,
    LogicalStateSignal,
    NodeMap,
    StateSignalKind,
    state_signal_kind,
)


class SimulatorScenario(str, Enum):
    NORMAL = "normal"
    DEGRADED_QUALITY = "degraded-quality"
    BAD_QUALITY = "bad-quality"
    STALE_TIMESTAMP = "stale"
    MISSING_NODE = "missing-node"
    WRONG_DATATYPE = "wrong-type"
    DISCONNECT_RECONNECT = "disconnect-reconnect"
    PARTIAL_MAPPING = "partial-good"
    VALUE_CHANGES = "value-changes"
    INVALID_NUMERIC = "invalid-numeric"


class SimulatorNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    logical_signal: str = Field(min_length=1, max_length=128)
    symbol_path: str = Field(min_length=1, max_length=512)
    node_id: str = Field(min_length=1, max_length=256)
    browse_name: str = Field(min_length=1, max_length=256)
    data_type: Literal["BOOL", "REAL", "STRING"]
    initial_value: bool | float | str
    writable: bool = False
    quality: Literal["good", "uncertain", "bad"] = "good"
    update_behavior: Literal["static", "controlled"] = "static"
    source_timestamp_behavior: Literal["current", "stale", "missing"] = "current"

    @field_validator("node_id")
    @classmethod
    def reject_placeholder_node_id(cls, value: str) -> str:
        normalized = value.upper()
        if any(marker in normalized for marker in ("TODO", "REPLACE_ME", "CONFIGURE_ME")):
            raise ValueError("placeholder simulator NodeIds are forbidden")
        return value.strip()

    @model_validator(mode="after")
    def validate_value_matches_type(self) -> "SimulatorNode":
        if self.data_type == "BOOL" and not isinstance(self.initial_value, bool):
            raise ValueError("BOOL simulator nodes require a boolean initial value")
        if self.data_type == "REAL" and (
            isinstance(self.initial_value, bool) or not isinstance(self.initial_value, float)
        ):
            raise ValueError("REAL simulator nodes require a floating-point initial value")
        if self.data_type == "STRING" and not isinstance(self.initial_value, str):
            raise ValueError("STRING simulator nodes require a string initial value")
        return self


class SimulatorFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    scenario: SimulatorScenario
    target: str | None = Field(default=None, min_length=1, max_length=128)
    nodes: tuple[SimulatorNode, ...] = ()

    @model_validator(mode="after")
    def unique_fixture_nodes(self) -> "SimulatorFixture":
        logical = [node.logical_signal for node in self.nodes]
        node_ids = [node.node_id for node in self.nodes]
        if len(logical) != len(set(logical)) or len(node_ids) != len(set(node_ids)):
            raise ValueError("simulator fixture logical signals and NodeIds must be unique")
        return self


TEST_VALUES = {
    LogicalSignal.ION_V: 4.5,
    LogicalSignal.ION_I: 1.8,
    LogicalSignal.HEAT_V: 7.0,
    LogicalSignal.HEAT_I: 3.2,
    LogicalSignal.HE_LEVEL: 68.0,
    LogicalSignal.T_HOT: 62.0,
    LogicalSignal.T_COLD: 28.0,
    LogicalSignal.CMPS_CURRENT: 8.4,
    LogicalSignal.CFPS_POWER: 350.0,
    LogicalSignal.IPPS_VOLTAGE: 4.5,
    LogicalSignal.IPPS_CURRENT: 1.8,
    LogicalSignal.AHVPS_VOLTAGE: 42.0,
    LogicalSignal.CHVPS_VOLTAGE: 18.0,
    LogicalSignal.PULSE_LENGTH: 2.5,
    LogicalSignal.PULSE_PERIOD: 1.0,
}

TEST_UNITS = {
    LogicalSignal.ION_V: "V",
    LogicalSignal.ION_I: "A",
    LogicalSignal.HEAT_V: "V",
    LogicalSignal.HEAT_I: "A",
    LogicalSignal.HE_LEVEL: "%",
    LogicalSignal.T_HOT: "degC",
    LogicalSignal.T_COLD: "degC",
    LogicalSignal.CMPS_CURRENT: "A",
    LogicalSignal.CFPS_POWER: "W",
    LogicalSignal.IPPS_VOLTAGE: "V",
    LogicalSignal.IPPS_CURRENT: "A",
    LogicalSignal.AHVPS_VOLTAGE: "kV",
    LogicalSignal.CHVPS_VOLTAGE: "kV",
    LogicalSignal.PULSE_LENGTH: "ms",
    LogicalSignal.PULSE_PERIOD: "s",
}

TEST_STATE_VALUES = {
    signal: False
    if state_signal_kind(signal) == StateSignalKind.ALARM
    or signal == LogicalStateSignal.POOR_VACUUM
    else True
    for signal in LogicalStateSignal
}


COMMISSIONING_STATE_PATHS = {
    LogicalStateSignal.CMPS_STATE: "Application.GVL_IntS.gIntS_Inp.CMPS_On",
    LogicalStateSignal.CMPS: "Application.GVL_IntS.gIntS_Outp.Auth_CMPS",
    LogicalStateSignal.CFPS_STATE: "Application.GVL_IntS.gIntS_Inp.CFPS_On",
    LogicalStateSignal.CFPS_FEEDBACK: "Application.PLC_PRG.filamentData.Sts_Run",
    LogicalStateSignal.CFPS_INTERLOCK: "Application.GVL_IntS.gIntS_Outp.Auth_CFPS",
    LogicalStateSignal.IPPS_STATE: "Application.GVL_IntS.gIntS_Inp.IPPS_On",
    LogicalStateSignal.IPPS: "Application.GVL_IntS.gIntS_Outp.Auth_IPPS",
    LogicalStateSignal.AHVPS_STATE: "Application.GVL_IntS.gIntS_Inp.APS_On",
    LogicalStateSignal.AHVPS_PROTECTION: "Application.GVL_Alarms.gAlarms.ApsFault",
    LogicalStateSignal.AHVPS_INTERLOCK: "Application.GVL_IntS.gIntS_Outp.Auth_APS",
    LogicalStateSignal.CHVPS_STATE: "Application.GVL_IntS.gIntS_Inp.CPS_On",
    LogicalStateSignal.CHVPS_PROTECTION: "Application.GVL_Alarms.gAlarms.CpsFault",
    LogicalStateSignal.CHVPS_INTERLOCK: "Application.GVL_IntS.gIntS_Outp.Auth_CPS",
}

COMMISSIONING_READING_PATHS = {
    LogicalSignal.IPPS_VOLTAGE: "Application.PLC_PRG.daqData.IonPumpVoltage_kV",
    LogicalSignal.IPPS_CURRENT: "Application.PLC_PRG.daqData.IonPumpCurrent_mA",
}


def unused_local_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _fixture_node_id(value: str, default_namespace: int) -> ua.NodeId:
    """Use exact supplied NodeIds when present; defaults remain test identifiers."""
    if ";" in value or value.startswith(("i=", "s=", "g=", "b=")):
        return ua.NodeId.from_string(value)
    return ua.NodeId(value, default_namespace)


def load_simulator_fixture(path: Path) -> SimulatorFixture:
    return SimulatorFixture.model_validate_json(path.read_text(encoding="utf-8"))


def commissioning_nodes(
    scenario: SimulatorScenario = SimulatorScenario.NORMAL,
    *,
    target: str | None = None,
    fixture: SimulatorFixture | None = None,
) -> tuple[SimulatorNode, ...]:
    if fixture is not None and fixture.nodes:
        return fixture.nodes
    if fixture is not None:
        scenario, target = fixture.scenario, fixture.target
    selected_target = target or "ipps.voltage"
    nodes: list[SimulatorNode] = []
    for signal, path in COMMISSIONING_STATE_PATHS.items():
        value = False if signal in {
            LogicalStateSignal.AHVPS_PROTECTION,
            LogicalStateSignal.CHVPS_PROTECTION,
        } else True
        nodes.append(
            SimulatorNode(
                logical_signal=signal.value,
                symbol_path=path,
                node_id=f"TestOnly.Commissioning.{signal.value}",
                browse_name=path.rsplit(".", 1)[-1],
                data_type="BOOL",
                initial_value=value,
                update_behavior=(
                    "controlled" if scenario == SimulatorScenario.VALUE_CHANGES else "static"
                ),
            )
        )
    for signal, path in COMMISSIONING_READING_PATHS.items():
        logical_name = signal.value
        data_type: Literal["REAL", "STRING"] = "REAL"
        value: float | str = 2.5 if signal == LogicalSignal.IPPS_VOLTAGE else 3.0
        quality: Literal["good", "uncertain", "bad"] = "good"
        timestamp: Literal["current", "stale", "missing"] = "current"
        if logical_name == selected_target:
            if scenario == SimulatorScenario.DEGRADED_QUALITY:
                quality = "uncertain"
            elif scenario == SimulatorScenario.BAD_QUALITY:
                quality = "bad"
            elif scenario == SimulatorScenario.STALE_TIMESTAMP:
                timestamp = "stale"
            elif scenario == SimulatorScenario.WRONG_DATATYPE:
                data_type, value = "STRING", "wrong-type"
            elif scenario == SimulatorScenario.INVALID_NUMERIC:
                value = float("nan")
        nodes.append(
            SimulatorNode(
                logical_signal=logical_name,
                symbol_path=path,
                node_id=f"TestOnly.Commissioning.{logical_name}",
                browse_name=path.rsplit(".", 1)[-1],
                data_type=data_type,
                initial_value=value,
                quality=quality,
                source_timestamp_behavior=timestamp,
                update_behavior=(
                    "controlled" if scenario == SimulatorScenario.VALUE_CHANGES else "static"
                ),
            )
        )
    return tuple(nodes)


class LocalOPCUASimulator:
    def __init__(
        self,
        port: int | None = None,
        *,
        integer_signal: LogicalSignal | None = None,
        telemetry_values: dict[LogicalSignal, float | int] | None = None,
        security_certificate_path: Path | None = None,
        security_private_key_path: Path | None = None,
        commissioning_scenario: SimulatorScenario | None = None,
        commissioning_target: str | None = None,
        commissioning_fixture: SimulatorFixture | None = None,
    ) -> None:
        self.port = port or unused_local_port()
        self.integer_signal = integer_signal
        self.telemetry_values = {**TEST_VALUES, **(telemetry_values or {})}
        self.endpoint_url = f"opc.tcp://127.0.0.1:{self.port}/gyrotron-test/"
        self.security_certificate_path = security_certificate_path
        self.security_private_key_path = security_private_key_path
        self.commissioning_scenario = (
            commissioning_fixture.scenario if commissioning_fixture else commissioning_scenario
        )
        self.commissioning_target = (
            commissioning_fixture.target if commissioning_fixture else commissioning_target
        )
        self.commissioning_fixture = commissioning_fixture
        self.server: Server | None = None
        self.node_ids: dict[LogicalSignal, str] = {}
        self.state_node_ids: dict[LogicalStateSignal, str] = {}
        self.state_values = dict(TEST_STATE_VALUES)
        self._commissioning_nodes: dict[str, SimulatorNode] = {}
        self._values: dict[str, bool | float | str] = {}
        self._node_objects: dict[str, object] = {}

    @classmethod
    def commissioning(
        cls,
        scenario: SimulatorScenario = SimulatorScenario.NORMAL,
        *,
        target: str | None = None,
        port: int | None = None,
        fixture: SimulatorFixture | None = None,
    ) -> "LocalOPCUASimulator":
        return cls(
            port=port,
            commissioning_scenario=scenario,
            commissioning_target=target,
            commissioning_fixture=fixture,
        )

    async def start(self) -> None:
        server = Server()
        await server.init()
        server.set_endpoint(self.endpoint_url)
        if self.security_certificate_path is not None:
            if self.security_private_key_path is None:
                raise ValueError("secure test server requires a private key")
            await server.load_certificate(self.security_certificate_path)
            await server.load_private_key(self.security_private_key_path)
            server.set_security_policy(
                [ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt]
            )
        namespace = await server.register_namespace("urn:gyrotron:test:readonly")
        gyrotron = await server.nodes.objects.add_object(namespace, "TestGyrotron")
        if self.commissioning_scenario is None:
            await self._add_legacy_nodes(server, gyrotron, namespace)
        else:
            await self._add_commissioning_nodes(server, gyrotron, namespace)
        await server.start()
        self.server = server

    async def _add_legacy_nodes(self, server: Server, parent, namespace: int) -> None:
        self.node_ids = {}
        for signal, value in self.telemetry_values.items():
            node_id = ua.NodeId(f"TestGyrotron.{signal.value}", namespace)
            server_value = int(value) if signal == self.integer_signal else value
            await parent.add_variable(node_id, signal.value, server_value)
            self.node_ids[signal] = node_id.to_string()
        self.state_node_ids = {}
        self.state_values = dict(TEST_STATE_VALUES)
        for signal, value in TEST_STATE_VALUES.items():
            node_id = ua.NodeId(f"TestGyrotron.State.{signal.value}", namespace)
            await parent.add_variable(node_id, signal.value, value)
            server.iserver.aspace.set_attribute_value_callback(
                node_id,
                ua.AttributeIds.Value,
                lambda _node_id, _attribute, signal=signal: self._state_data_value(signal),
            )
            self.state_node_ids[signal] = node_id.to_string()

    async def _add_commissioning_nodes(self, server: Server, parent, namespace: int) -> None:
        definitions = commissioning_nodes(
            self.commissioning_scenario or SimulatorScenario.NORMAL,
            target=self.commissioning_target,
            fixture=self.commissioning_fixture,
        )
        self._commissioning_nodes = {node.logical_signal: node for node in definitions}
        self._values = {node.logical_signal: node.initial_value for node in definitions}
        self._node_objects = {}
        self.node_ids = {}
        self.state_node_ids = {}

        for signal in (
            LogicalSignal.ION_V,
            LogicalSignal.ION_I,
            LogicalSignal.HEAT_V,
            LogicalSignal.HEAT_I,
            LogicalSignal.HE_LEVEL,
            LogicalSignal.T_HOT,
            LogicalSignal.T_COLD,
        ):
            node_id = ua.NodeId(f"TestOnly.Support.{signal.value}", namespace)
            await parent.add_variable(node_id, signal.value, float(TEST_VALUES[signal]))
            self.node_ids[signal] = node_id.to_string()

        missing_target = (
            (self.commissioning_target or "ipps.voltage")
            if self.commissioning_scenario == SimulatorScenario.MISSING_NODE
            else None
        )
        for definition in definitions:
            node_id = _fixture_node_id(definition.node_id, namespace)
            logical = definition.logical_signal
            if logical in {signal.value for signal in LogicalSignal}:
                self.node_ids[LogicalSignal(logical)] = node_id.to_string()
            else:
                self.state_node_ids[LogicalStateSignal(logical)] = node_id.to_string()
            if logical == missing_target:
                continue
            variant_type = {
                "BOOL": ua.VariantType.Boolean,
                "REAL": ua.VariantType.Float,
                "STRING": ua.VariantType.String,
            }[definition.data_type]
            node = await parent.add_variable(
                node_id,
                definition.browse_name,
                definition.initial_value,
                varianttype=variant_type,
            )
            if definition.writable:
                await node.set_writable()
            server.iserver.aspace.set_attribute_value_callback(
                node_id,
                ua.AttributeIds.Value,
                lambda _node_id, _attribute, logical=logical: self._commissioning_data_value(
                    logical
                ),
            )
            self._node_objects[logical] = node

    def _commissioning_data_value(self, logical_signal: str) -> ua.DataValue:
        definition = self._commissioning_nodes[logical_signal]
        value = self._values[logical_signal]
        status = {
            "good": ua.StatusCodes.Good,
            "uncertain": ua.StatusCodes.UncertainDataSubNormal,
            "bad": ua.StatusCodes.BadSensorFailure,
        }[definition.quality]
        now = datetime.now(timezone.utc)
        source_timestamp = {
            "current": now,
            "stale": now - timedelta(minutes=10),
            "missing": None,
        }[definition.source_timestamp_behavior]
        variant_type = {
            "BOOL": ua.VariantType.Boolean,
            "REAL": ua.VariantType.Float,
            "STRING": ua.VariantType.String,
        }[definition.data_type]
        return ua.DataValue(
            Value=ua.Variant(value, variant_type),
            StatusCode=ua.StatusCode(status),
            SourceTimestamp=source_timestamp,
            ServerTimestamp=now,
        )

    async def stop(self) -> None:
        server, self.server = self.server, None
        if server is not None:
            await server.stop()

    async def crash(self) -> None:
        """Stop the localhost endpoint to exercise loss and recovery."""
        server, self.server = self.server, None
        if server is None:
            return
        await asyncio.wait_for(server.stop(), timeout=2)

    async def publish_value_for_test(
        self, logical_signal: str, value: bool | float | str
    ) -> None:
        if logical_signal not in self._values:
            raise KeyError(logical_signal)
        self._values[logical_signal] = value
        await asyncio.sleep(0)

    def commissioning_node_map(self) -> NodeMap:
        if self.commissioning_scenario is None:
            raise ValueError("commissioning_node_map requires a commissioning scenario")
        selected_readings = set(COMMISSIONING_READING_PATHS)
        selected_states = set(COMMISSIONING_STATE_PATHS)
        if self.commissioning_scenario == SimulatorScenario.PARTIAL_MAPPING:
            selected_readings = {
                LogicalSignal.IPPS_VOLTAGE,
                LogicalSignal.IPPS_CURRENT,
            }
            selected_states = {
                LogicalStateSignal.CMPS_STATE,
                LogicalStateSignal.CMPS,
                LogicalStateSignal.IPPS_STATE,
                LogicalStateSignal.IPPS,
            }
        support = {
            LogicalSignal.ION_V,
            LogicalSignal.ION_I,
            LogicalSignal.HEAT_V,
            LogicalSignal.HEAT_I,
            LogicalSignal.HE_LEVEL,
            LogicalSignal.T_HOT,
            LogicalSignal.T_COLD,
        }
        mappings = [
            {
                "signal": signal,
                "node_id": self.node_ids[signal],
                "expected_type": "float",
                "unit": TEST_UNITS[signal],
                "scale": (
                    1000.0
                    if signal == LogicalSignal.IPPS_VOLTAGE
                    else 0.001
                    if signal == LogicalSignal.IPPS_CURRENT
                    else 1.0
                ),
            }
            for signal in sorted(support | selected_readings, key=lambda item: item.value)
        ]
        states = []
        for signal in sorted(selected_states, key=lambda item: item.value):
            if signal in {
                LogicalStateSignal.AHVPS_PROTECTION,
                LogicalStateSignal.CHVPS_PROTECTION,
            }:
                interpretation = {"true": "fault", "false": "ok"}
            elif signal.value.endswith(".state"):
                interpretation = {"true": "on", "false": "off"}
            else:
                interpretation = {"true": "ok", "false": "fault"}
            states.append(
                {
                    "signal": signal,
                    "node_id": self.state_node_ids[signal],
                    "expected_type": "boolean",
                    "interpretation": interpretation,
                }
            )
        return NodeMap(
            schema_version=1,
            purpose="test",
            signals=mappings,
            state_signals=states,
        )

    def node_map(
        self,
        *,
        missing: LogicalSignal | None = None,
        unavailable: LogicalSignal | None = None,
        integer_type: LogicalSignal | None = None,
        telemetry_signals: set[LogicalSignal] | None = None,
        state_signals: set[LogicalStateSignal] | None = None,
        state_missing: LogicalStateSignal | None = None,
        state_unavailable: LogicalStateSignal | None = None,
    ) -> NodeMap:
        if self.commissioning_scenario is not None:
            return self.commissioning_node_map()
        mappings = []
        selected_telemetry = set(self.node_ids) if telemetry_signals is None else telemetry_signals
        for signal in LogicalSignal:
            if signal not in selected_telemetry:
                continue
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
        allow_insecure_localhost=True,
    )
