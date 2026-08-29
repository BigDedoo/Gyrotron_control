import math
import re
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import AlarmSeverity, InterpretedState


class NodeMapError(ValueError):
    pass


class LogicalSignal(str, Enum):
    ION_V = "ionV"
    ION_I = "ionI"
    HEAT_V = "heatV"
    HEAT_I = "heatI"
    HE_LEVEL = "heLvl"
    T_HOT = "Thot"
    T_COLD = "Tcold"
    CMPS_CURRENT = "cmps.current"
    CFPS_POWER = "cfps.power"
    IPPS_VOLTAGE = "ipps.voltage"
    IPPS_CURRENT = "ipps.current"
    AHVPS_VOLTAGE = "ahvps.voltage"
    CHVPS_VOLTAGE = "chvps.voltage"
    PULSE_LENGTH = "pulse_generator.length"
    PULSE_PERIOD = "pulse_generator.period"


REQUIRED_SIGNALS = frozenset(
    {
        LogicalSignal.ION_V,
        LogicalSignal.ION_I,
        LogicalSignal.HEAT_V,
        LogicalSignal.HEAT_I,
        LogicalSignal.HE_LEVEL,
        LogicalSignal.T_HOT,
        LogicalSignal.T_COLD,
    }
)

EQUIPMENT_SIGNAL_UNITS = {
    LogicalSignal.CMPS_CURRENT: "A",
    LogicalSignal.CFPS_POWER: "W",
    LogicalSignal.IPPS_VOLTAGE: "V",
    LogicalSignal.IPPS_CURRENT: "A",
    LogicalSignal.AHVPS_VOLTAGE: "kV",
    LogicalSignal.CHVPS_VOLTAGE: "kV",
    LogicalSignal.PULSE_LENGTH: "ms",
    LogicalSignal.PULSE_PERIOD: "s",
}


class ExpectedType(str, Enum):
    FLOAT = "float"
    INTEGER = "integer"


class StateExpectedType(str, Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"


class StateSignalKind(str, Enum):
    COMPONENT = "component"
    INTERLOCK = "interlock"
    ALARM = "alarm"


class LogicalStateSignal(str, Enum):
    CPS_STATE = "cps.state"
    CPS_READY = "cps.ready"
    CPS_RECTIFIER = "cps.rectifier"
    CPS_CONVERTER = "cps.converter"
    CPS_PROTECTION = "cps.protection"
    APS_STATE = "aps.state"
    APS_READY = "aps.ready"
    APS_RECTIFIER = "aps.rectifier"
    APS_CONVERTER = "aps.converter"
    APS_PROTECTION = "aps.protection"
    EXTERNAL_INTERLOCK = "interlock.external"
    GS_DOORS = "interlock.gs_doors"
    WATERFLOW = "interlock.waterflow"
    POOR_VACUUM = "interlock.poor_vacuum"
    CMPS = "interlock.cmps"
    GPPS = "interlock.gpps"
    IPPS = "interlock.ipps"
    CPS_SUPPLY = "interlock.cps"
    APS_SUPPLY = "interlock.aps"
    LIQUID_HE_GAUGE = "interlock.liquid_he_gauge"
    HE_LEVEL_NORMAL = "interlock.he_level_normal"
    ARC_DETECTOR = "alarm.arc_detector"
    OVERCURRENT = "alarm.overcurrent"
    OVERVOLTAGE = "alarm.overvoltage"
    TEMPERATURE = "alarm.temperature"
    CMPS_STATE = "cmps.state"
    CFPS_STATE = "cfps.state"
    CFPS_FEEDBACK = "cfps.feedback"
    CFPS_INTERLOCK = "interlock.cfps"
    IPPS_STATE = "ipps.state"
    AHVPS_STATE = "ahvps.state"
    AHVPS_PROTECTION = "ahvps.protection"
    AHVPS_INTERLOCK = "interlock.ahvps"
    CHVPS_STATE = "chvps.state"
    CHVPS_PROTECTION = "chvps.protection"
    CHVPS_INTERLOCK = "interlock.chvps"
    PULSE_GENERATOR_STATE = "pulse_generator.state"
    PULSE_GENERATOR_FEEDBACK = "pulse_generator.feedback"


STATE_SIGNAL_METADATA: dict[LogicalStateSignal, tuple[StateSignalKind, str, str]] = {
    LogicalStateSignal.CPS_STATE: (StateSignalKind.COMPONENT, "CPS", "Overall"),
    LogicalStateSignal.CPS_READY: (StateSignalKind.COMPONENT, "CPS", "Ready"),
    LogicalStateSignal.CPS_RECTIFIER: (StateSignalKind.COMPONENT, "CPS", "Power Rectifier"),
    LogicalStateSignal.CPS_CONVERTER: (StateSignalKind.COMPONENT, "CPS", "Charging Converter"),
    LogicalStateSignal.CPS_PROTECTION: (StateSignalKind.COMPONENT, "CPS", "Protection"),
    LogicalStateSignal.APS_STATE: (StateSignalKind.COMPONENT, "APS", "Overall"),
    LogicalStateSignal.APS_READY: (StateSignalKind.COMPONENT, "APS", "Ready"),
    LogicalStateSignal.APS_RECTIFIER: (StateSignalKind.COMPONENT, "APS", "Power Rectifier"),
    LogicalStateSignal.APS_CONVERTER: (StateSignalKind.COMPONENT, "APS", "Charging Converter"),
    LogicalStateSignal.APS_PROTECTION: (StateSignalKind.COMPONENT, "APS", "Protection"),
    LogicalStateSignal.EXTERNAL_INTERLOCK: (StateSignalKind.INTERLOCK, "Environment", "External interlock"),
    LogicalStateSignal.GS_DOORS: (StateSignalKind.INTERLOCK, "Environment", "GS Doors"),
    LogicalStateSignal.WATERFLOW: (StateSignalKind.INTERLOCK, "Environment", "Waterflow"),
    LogicalStateSignal.POOR_VACUUM: (StateSignalKind.INTERLOCK, "Environment", "Poor vacuum"),
    LogicalStateSignal.CMPS: (StateSignalKind.INTERLOCK, "Supplies", "CMPS"),
    LogicalStateSignal.GPPS: (StateSignalKind.INTERLOCK, "Supplies", "GPPS"),
    LogicalStateSignal.IPPS: (StateSignalKind.INTERLOCK, "Supplies", "IPPS"),
    LogicalStateSignal.CPS_SUPPLY: (StateSignalKind.INTERLOCK, "Supplies", "CPS"),
    LogicalStateSignal.APS_SUPPLY: (StateSignalKind.INTERLOCK, "Supplies", "APS"),
    LogicalStateSignal.LIQUID_HE_GAUGE: (StateSignalKind.INTERLOCK, "Cryo", "Liquid He gauge"),
    LogicalStateSignal.HE_LEVEL_NORMAL: (StateSignalKind.INTERLOCK, "Cryo", "He level normal"),
    LogicalStateSignal.ARC_DETECTOR: (StateSignalKind.ALARM, "Alarms", "ARC detector"),
    LogicalStateSignal.OVERCURRENT: (StateSignalKind.ALARM, "Alarms", "Overcurrent"),
    LogicalStateSignal.OVERVOLTAGE: (StateSignalKind.ALARM, "Alarms", "Overvoltage"),
    LogicalStateSignal.TEMPERATURE: (StateSignalKind.ALARM, "Alarms", "Temperature"),
    LogicalStateSignal.CMPS_STATE: (StateSignalKind.COMPONENT, "CMPS", "State"),
    LogicalStateSignal.CFPS_STATE: (StateSignalKind.COMPONENT, "CFPS", "State"),
    LogicalStateSignal.CFPS_FEEDBACK: (StateSignalKind.COMPONENT, "CFPS", "Feedback"),
    LogicalStateSignal.CFPS_INTERLOCK: (StateSignalKind.INTERLOCK, "Supplies", "CFPS"),
    LogicalStateSignal.IPPS_STATE: (StateSignalKind.COMPONENT, "IPPS", "State"),
    LogicalStateSignal.AHVPS_STATE: (StateSignalKind.COMPONENT, "AHVPS", "State"),
    LogicalStateSignal.AHVPS_PROTECTION: (
        StateSignalKind.COMPONENT,
        "AHVPS",
        "Protection",
    ),
    LogicalStateSignal.AHVPS_INTERLOCK: (
        StateSignalKind.INTERLOCK,
        "Supplies",
        "AHVPS",
    ),
    LogicalStateSignal.CHVPS_STATE: (StateSignalKind.COMPONENT, "CHVPS", "State"),
    LogicalStateSignal.CHVPS_PROTECTION: (
        StateSignalKind.COMPONENT,
        "CHVPS",
        "Protection",
    ),
    LogicalStateSignal.CHVPS_INTERLOCK: (
        StateSignalKind.INTERLOCK,
        "Supplies",
        "CHVPS",
    ),
    LogicalStateSignal.PULSE_GENERATOR_STATE: (
        StateSignalKind.COMPONENT,
        "Pulse Generator",
        "State",
    ),
    LogicalStateSignal.PULSE_GENERATOR_FEEDBACK: (
        StateSignalKind.COMPONENT,
        "Pulse Generator",
        "Feedback",
    ),
}


def state_signal_kind(signal: LogicalStateSignal) -> StateSignalKind:
    return STATE_SIGNAL_METADATA[signal][0]


def state_signal_group(signal: LogicalStateSignal) -> str:
    return STATE_SIGNAL_METADATA[signal][1]


def state_signal_label(signal: LogicalStateSignal) -> str:
    return STATE_SIGNAL_METADATA[signal][2]


class NodeMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    signal: LogicalSignal
    node_id: str = Field(min_length=1, max_length=512)
    expected_type: ExpectedType
    unit: str = Field(min_length=1, max_length=32)
    scale: float = 1.0
    offset: float = 0.0

    @field_validator("node_id", "unit")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("node_id")
    @classmethod
    def reject_placeholder_node_ids(cls, value: str) -> str:
        normalized = value.upper()
        placeholders = ("TODO", "REPLACE_ME", "CONFIGURE_ME", "PLACEHOLDER")
        if any(marker in normalized for marker in placeholders):
            raise ValueError("placeholder node IDs are not permitted")
        if not (";" in value or value.startswith("i=") or value.startswith("s=")):
            raise ValueError("node_id must use an OPC UA NodeId string")
        return value

    @field_validator("unit")
    @classmethod
    def reject_placeholder_units(cls, value: str) -> str:
        if any(marker in value.upper() for marker in ("TODO", "REPLACE_ME", "CONFIGURE_ME")):
            raise ValueError("placeholder engineering units are not permitted")
        return value

    @field_validator("scale")
    @classmethod
    def validate_scale(cls, value: float) -> float:
        if not math.isfinite(value) or value == 0:
            raise ValueError("scale must be finite and non-zero")
        return value

    @field_validator("offset")
    @classmethod
    def validate_offset(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("offset must be finite")
        return value

    @model_validator(mode="after")
    def validate_equipment_unit(self) -> "NodeMapping":
        expected = EQUIPMENT_SIGNAL_UNITS.get(self.signal)
        if expected is not None and self.unit != expected:
            raise ValueError(
                f"{self.signal.value} must use the established engineering unit {expected}"
            )
        return self


class StateNodeMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    signal: LogicalStateSignal
    node_id: str = Field(min_length=1, max_length=512)
    expected_type: StateExpectedType
    interpretation: dict[str, InterpretedState]
    display_label: str | None = Field(default=None, min_length=1, max_length=128)
    group: str | None = Field(default=None, min_length=1, max_length=128)
    alarm_severity: AlarmSeverity | None = None

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, value: str) -> str:
        value = value.strip()
        normalized = value.upper()
        if any(
            marker in normalized
            for marker in ("TODO", "REPLACE_ME", "CONFIGURE_ME", "PLACEHOLDER")
        ):
            raise ValueError("placeholder node IDs are not permitted")
        if not (";" in value or value.startswith("i=") or value.startswith("s=")):
            raise ValueError("node_id must use an OPC UA NodeId string")
        return value

    @field_validator("display_label", "group")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def validate_interpretation(self) -> "StateNodeMapping":
        if self.expected_type == StateExpectedType.BOOLEAN:
            if set(self.interpretation) != {"true", "false"}:
                raise ValueError("boolean state mappings require explicit true and false interpretation")
        else:
            if not self.interpretation:
                raise ValueError("integer state mappings require an explicit enum interpretation")
            for raw_key in self.interpretation:
                if re.fullmatch(r"-?(0|[1-9][0-9]*)", raw_key) is None:
                    raise ValueError("integer interpretation keys must be canonical base-10 integers")

        kind = state_signal_kind(self.signal)
        if kind == StateSignalKind.ALARM:
            allowed = {InterpretedState.ACTIVE, InterpretedState.INACTIVE}
        elif self.signal.value.endswith((".state", ".rectifier", ".converter")):
            allowed = {InterpretedState.ON, InterpretedState.OFF, InterpretedState.FAULT}
        else:
            allowed = {InterpretedState.OK, InterpretedState.FAULT}
        if not set(self.interpretation.values()).issubset(allowed):
            expected = ", ".join(sorted(state.value for state in allowed))
            raise ValueError(f"interpretation for {self.signal.value} must use only: {expected}")
        if kind != StateSignalKind.ALARM and self.alarm_severity is not None:
            raise ValueError("alarm_severity is only valid for alarm signals")
        return self

    @property
    def label(self) -> str:
        return self.display_label or state_signal_label(self.signal)

    @property
    def display_group(self) -> str:
        return self.group or state_signal_group(self.signal)

    def interpret(self, raw: bool | int) -> InterpretedState:
        if self.expected_type == StateExpectedType.BOOLEAN:
            key = "true" if raw is True else "false"
        else:
            key = str(raw)
        return self.interpretation.get(key, InterpretedState.UNKNOWN)


class NodeMap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: int = Field(ge=1, le=1)
    purpose: str = Field(min_length=1, max_length=32)
    signals: tuple[NodeMapping, ...]
    state_signals: tuple[StateNodeMapping, ...] = ()

    @field_validator("purpose")
    @classmethod
    def normalize_purpose(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_mappings(self) -> "NodeMap":
        signal_names = [mapping.signal for mapping in self.signals]
        state_signal_names = [mapping.signal for mapping in self.state_signals]
        node_ids = [mapping.node_id for mapping in (*self.signals, *self.state_signals)]
        if len(signal_names) != len(set(signal_names)):
            raise ValueError("logical signal mappings must be unique")
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("OPC UA node IDs must be unique")
        if len(state_signal_names) != len(set(state_signal_names)):
            raise ValueError("logical state signal mappings must be unique")
        missing = REQUIRED_SIGNALS.difference(signal_names)
        if missing:
            missing_text = ", ".join(sorted(signal.value for signal in missing)) or "none"
            raise ValueError(f"node map signal mismatch (missing: {missing_text})")
        if self.purpose == "production" and any(
            "TESTONLY" in mapping.node_id.upper() or "TEST_ONLY" in mapping.node_id.upper()
            for mapping in (*self.signals, *self.state_signals)
        ):
            raise ValueError("test-only node IDs cannot be activated in a production map")
        return self

    def by_signal(self) -> dict[LogicalSignal, NodeMapping]:
        return {mapping.signal: mapping for mapping in self.signals}

    def states_by_signal(self) -> dict[LogicalStateSignal, StateNodeMapping]:
        return {mapping.signal: mapping for mapping in self.state_signals}


def load_node_map(path: Path, *, allowed_purposes: frozenset[str] = frozenset({"production"})) -> NodeMap:
    try:
        raw = path.read_text(encoding="utf-8")
        node_map = NodeMap.model_validate_json(raw)
    except (OSError, ValueError) as exc:
        raise NodeMapError(f"Invalid OPC UA node map: {path.name}") from exc
    if node_map.purpose not in allowed_purposes:
        allowed = ", ".join(sorted(allowed_purposes))
        raise NodeMapError(
            f"OPC UA node map purpose '{node_map.purpose}' is not allowed; expected {allowed}"
        )
    return node_map
