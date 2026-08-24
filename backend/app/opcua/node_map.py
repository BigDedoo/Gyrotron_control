import math
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


REQUIRED_SIGNALS = frozenset(LogicalSignal)


class ExpectedType(str, Enum):
    FLOAT = "float"
    INTEGER = "integer"


class NodeMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

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


class NodeMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = Field(ge=1, le=1)
    purpose: str = Field(min_length=1, max_length=32)
    signals: tuple[NodeMapping, ...]

    @field_validator("purpose")
    @classmethod
    def normalize_purpose(cls, value: str) -> str:
        return value.strip().lower()

    @model_validator(mode="after")
    def validate_mappings(self) -> "NodeMap":
        signal_names = [mapping.signal for mapping in self.signals]
        node_ids = [mapping.node_id for mapping in self.signals]
        if len(signal_names) != len(set(signal_names)):
            raise ValueError("logical signal mappings must be unique")
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("OPC UA node IDs must be unique")
        missing = REQUIRED_SIGNALS.difference(signal_names)
        extra = set(signal_names).difference(REQUIRED_SIGNALS)
        if missing or extra:
            missing_text = ", ".join(sorted(signal.value for signal in missing)) or "none"
            extra_text = ", ".join(sorted(signal.value for signal in extra)) or "none"
            raise ValueError(f"node map signal mismatch (missing: {missing_text}; extra: {extra_text})")
        if self.purpose == "production" and any(
            "TESTONLY" in mapping.node_id.upper() or "TEST_ONLY" in mapping.node_id.upper()
            for mapping in self.signals
        ):
            raise ValueError("test-only node IDs cannot be activated in a production map")
        return self

    def by_signal(self) -> dict[LogicalSignal, NodeMapping]:
        return {mapping.signal: mapping for mapping in self.signals}


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
