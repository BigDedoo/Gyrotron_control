from __future__ import annotations

import json
from collections import defaultdict
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.opcua.commissioning import (
    CommissioningField,
    ProductionCommissioningTemplate,
    load_commissioning_template,
)


class DiscoveredNodeError(ValueError):
    pass


class ReconciliationStatus(str, Enum):
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"
    DATATYPE_MISMATCH = "DATATYPE_MISMATCH"
    ACCESS_WARNING = "ACCESS_WARNING"
    UNIT_WARNING = "UNIT_WARNING"
    READY_FOR_DRAFT_MAP = "READY_FOR_DRAFT_MAP"


class DiscoveredNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol_path: str = Field(min_length=1, max_length=512)
    node_id: str = Field(min_length=1, max_length=512)
    namespace_uri: str = Field(min_length=1, max_length=512)
    namespace_index: int = Field(ge=0, le=65535)
    browse_name: str = Field(min_length=1, max_length=512)
    display_name: str = Field(min_length=1, max_length=512)
    data_type: str = Field(min_length=1, max_length=128)
    access_level: str = Field(min_length=1, max_length=128)
    user_access_level: str = Field(min_length=1, max_length=128)
    engineering_unit: str | None = Field(default=None, min_length=1, max_length=64)
    source_timestamp_observed: bool | None = None

    @field_validator(
        "symbol_path",
        "node_id",
        "namespace_uri",
        "browse_name",
        "display_name",
        "data_type",
        "access_level",
        "user_access_level",
        "engineering_unit",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("node_id")
    @classmethod
    def validate_node_id(cls, value: str) -> str:
        normalized = value.upper()
        if any(marker in normalized for marker in ("TODO", "REPLACE_ME", "CONFIGURE_ME")):
            raise ValueError("placeholder NodeIds are forbidden")
        if not (";" in value or value.startswith("i=") or value.startswith("s=")):
            raise ValueError("node_id must use an OPC UA NodeId string")
        return value


class DiscoveredNodeSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    source_format: Literal["canonical-json"]
    captured_offline: Literal[True]
    nodes: tuple[DiscoveredNode, ...]

    @model_validator(mode="after")
    def require_unique_node_ids(self) -> "DiscoveredNodeSet":
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("discovered NodeIds must be unique")
        return self


class ReconciledField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    equipment: str
    hmi_field: str
    logical_signal: str
    expected_symbol_path: str
    discovered_node_id: str | None
    expected_data_type: str
    observed_data_type: str | None
    access_level: str | None
    user_access_level: str | None
    expected_native_unit: str | None
    observed_engineering_unit: str | None
    conversion: dict[str, str] | None
    status: ReconciliationStatus
    detail: str


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_format: str
    expected_count: int
    ready_count: int
    fields: tuple[ReconciledField, ...]

    @property
    def ready_for_draft(self) -> tuple[ReconciledField, ...]:
        return tuple(
            field
            for field in self.fields
            if field.status == ReconciliationStatus.READY_FOR_DRAFT_MAP
        )


_BOOL_TYPES = frozenset({"bool", "boolean"})
_REAL_TYPES = frozenset({"real", "float", "double"})


def load_discovered_nodes(path: Path) -> DiscoveredNodeSet:
    try:
        return DiscoveredNodeSet.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DiscoveredNodeError(f"Invalid canonical discovered-node file: {path.name}") from exc


def _compatible_data_type(expected: str, observed: str) -> bool:
    normalized_expected = expected.strip().casefold()
    normalized_observed = observed.strip().casefold()
    if normalized_expected == "bool":
        return normalized_observed in _BOOL_TYPES
    if normalized_expected == "real":
        return normalized_observed in _REAL_TYPES
    return normalized_expected == normalized_observed


def _access_warning(node: DiscoveredNode) -> str | None:
    access = node.access_level.casefold()
    user_access = node.user_access_level.casefold()
    if "read" not in access or "read" not in user_access:
        return "Telemetry is not effectively readable by the application identity."
    if "write" in user_access:
        return "The application identity has effective write access; use a read-only identity."
    return None


def _conversion(field: CommissioningField) -> dict[str, str] | None:
    value = field.conversion.value
    if isinstance(value, dict):
        return dict(value)
    return None


def reconcile_discovered_nodes(
    template: ProductionCommissioningTemplate,
    discovered: DiscoveredNodeSet,
) -> ReconciliationResult:
    by_path: dict[str, list[DiscoveredNode]] = defaultdict(list)
    for node in discovered.nodes:
        by_path[node.symbol_path].append(node)

    expected = tuple(field for field in template.fields if field.exported_symbol_path.ready)
    reconciled: list[ReconciledField] = []
    for field in expected:
        symbol_path = str(field.exported_symbol_path.value)
        matches = by_path.get(symbol_path, [])
        expected_type = str(field.plc_type.value)
        expected_unit = (
            str(field.native_unit.value) if field.native_unit.value is not None else None
        )
        node: DiscoveredNode | None = matches[0] if len(matches) == 1 else None
        if not matches:
            status = ReconciliationStatus.MISSING
            detail = "No exact exported-symbol-path match was found."
        elif len(matches) > 1:
            status = ReconciliationStatus.AMBIGUOUS
            detail = f"{len(matches)} exact matches require human review."
        elif not _compatible_data_type(expected_type, node.data_type):
            status = ReconciliationStatus.DATATYPE_MISMATCH
            detail = f"Expected {expected_type}; observed {node.data_type}."
        elif warning := _access_warning(node):
            status = ReconciliationStatus.ACCESS_WARNING
            detail = warning
        elif expected_unit is not None and node.engineering_unit != expected_unit:
            status = ReconciliationStatus.UNIT_WARNING
            detail = (
                f"Expected native unit {expected_unit}; observed "
                f"{node.engineering_unit or 'no engineering-unit metadata'}."
            )
        else:
            status = ReconciliationStatus.READY_FOR_DRAFT_MAP
            detail = "Exact path, datatype, access, and required unit checks passed."

        reconciled.append(
            ReconciledField(
                equipment=field.equipment,
                hmi_field=field.field,
                logical_signal=field.logical_signal,
                expected_symbol_path=symbol_path,
                discovered_node_id=node.node_id if node is not None else None,
                expected_data_type=expected_type,
                observed_data_type=node.data_type if node is not None else None,
                access_level=node.access_level if node is not None else None,
                user_access_level=node.user_access_level if node is not None else None,
                expected_native_unit=expected_unit,
                observed_engineering_unit=(
                    node.engineering_unit if node is not None else None
                ),
                conversion=_conversion(field),
                status=status,
                detail=detail,
            )
        )

    return ReconciliationResult(
        source_format=discovered.source_format,
        expected_count=len(expected),
        ready_count=sum(
            field.status == ReconciliationStatus.READY_FOR_DRAFT_MAP
            for field in reconciled
        ),
        fields=tuple(reconciled),
    )


_STATE_DRAFT_CONFIG: dict[str, dict[str, object]] = {
    "cmps.state": {"interpretation": {"true": "on", "false": "off"}},
    "interlock.cmps": {"interpretation": {"true": "ok", "false": "fault"}},
    "cfps.state": {"interpretation": {"true": "on", "false": "off"}},
    "cfps.feedback": {"interpretation": {"true": "ok", "false": "fault"}},
    "interlock.cfps": {"interpretation": {"true": "ok", "false": "fault"}},
    "ipps.state": {"interpretation": {"true": "on", "false": "off"}},
    "interlock.ipps": {"interpretation": {"true": "ok", "false": "fault"}},
    "ahvps.state": {"interpretation": {"true": "on", "false": "off"}},
    "ahvps.protection": {"interpretation": {"true": "fault", "false": "ok"}},
    "interlock.ahvps": {"interpretation": {"true": "ok", "false": "fault"}},
    "chvps.state": {"interpretation": {"true": "on", "false": "off"}},
    "chvps.protection": {"interpretation": {"true": "fault", "false": "ok"}},
    "interlock.chvps": {"interpretation": {"true": "ok", "false": "fault"}},
}


def generate_draft_map(result: ReconciliationResult) -> dict[str, object]:
    signals: list[dict[str, object]] = []
    state_signals: list[dict[str, object]] = []
    symbol_evidence: dict[str, str] = {}
    for field in result.ready_for_draft:
        if field.discovered_node_id is None:
            continue
        symbol_evidence[field.logical_signal] = field.expected_symbol_path
        if field.logical_signal in {"ipps.voltage", "ipps.current"}:
            conversion = field.conversion or {}
            signals.append(
                {
                    "signal": field.logical_signal,
                    "node_id": field.discovered_node_id,
                    "expected_type": "float",
                    "unit": "V" if field.logical_signal == "ipps.voltage" else "A",
                    "scale": float(conversion["scale"]),
                    "offset": float(conversion["offset"]),
                }
            )
            continue
        config = _STATE_DRAFT_CONFIG.get(field.logical_signal)
        if config is None:
            continue
        state_signals.append(
            {
                "signal": field.logical_signal,
                "node_id": field.discovered_node_id,
                "expected_type": "boolean",
                **config,
            }
        )

    return {
        "schema_version": 1,
        "purpose": "draft-production",
        "approved": False,
        "warning": (
            "NON-RUNNABLE DRAFT. Human review and independent strict production-map "
            "construction are required."
        ),
        "source_format": result.source_format,
        "symbol_evidence": symbol_evidence,
        "signals": signals,
        "state_signals": state_signals,
    }


def render_reconciliation_report(result: ReconciliationResult) -> str:
    rows = []
    for field in result.fields:
        conversion = (
            "; ".join(f"{key}={value}" for key, value in field.conversion.items())
            if field.conversion
            else "NOT APPLICABLE"
        )
        rows.append(
            "| "
            + " | ".join(
                (
                    field.logical_signal,
                    field.expected_symbol_path,
                    field.discovered_node_id or "NOT FOUND",
                    field.expected_data_type,
                    field.observed_data_type or "UNKNOWN",
                    field.access_level or "UNKNOWN",
                    field.user_access_level or "UNKNOWN",
                    conversion,
                    field.status.value,
                )
            )
            + " |"
        )
    return "\n".join(
        (
            "# Offline OPC UA discovered-node reconciliation",
            "",
            "> Exact exported CODESYS symbol paths are the only automatic match key. No network calls or fuzzy auto-mapping are used.",
            "",
            f"- Expected exported fields: `{result.expected_count}`",
            f"- Ready for non-runnable draft: `{result.ready_count}`",
            "",
            "| HMI field | Expected CODESYS path | Discovered NodeId | Expected type | Observed type | AccessLevel | UserAccessLevel | Conversion | Status |",
            "|---|---|---|---|---|---|---|---|---|",
            *rows,
            "",
            "A `READY_FOR_DRAFT_MAP` result is not production approval. Effective write access is never tested by writing.",
        )
    )


def reconcile_files(template_path: Path, discovered_path: Path) -> ReconciliationResult:
    return reconcile_discovered_nodes(
        load_commissioning_template(template_path),
        load_discovered_nodes(discovered_path),
    )


def write_json(path: Path, payload: BaseModel | dict[str, object]) -> None:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
