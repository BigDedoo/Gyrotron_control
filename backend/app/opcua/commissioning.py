from __future__ import annotations

import argparse
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CommissioningTemplateError(ValueError):
    pass


class Confidence(str, Enum):
    CONFIRMED = "confirmed"
    STRONGLY_INFERRED = "strongly_inferred"
    WEAKLY_INFERRED = "weakly_inferred"
    UNKNOWN = "unknown"


class PhysicalSourceStatus(str, Enum):
    CANDIDATE_AVAILABLE = "candidate_available"
    SELECTION_UNRESOLVED = "selection_unresolved"
    NOT_RECOVERED = "not_recovered"


class Requirement(str, Enum):
    NODE_ID = "node_id"
    TYPE = "type"
    CONVERSION = "conversion"
    RANGE = "range"
    INTERPRETATION = "interpretation"
    POLARITY = "polarity"
    SIGNAL_SELECTION = "signal_selection"
    AGGREGATION = "aggregation"
    LATCHING = "latching"
    RECOVERY = "recovery"
    SEVERITY = "severity"


class ReadinessBlocker(str, Enum):
    NEEDS_NODE_ID = "NEEDS_NODE_ID"
    NEEDS_TYPE = "NEEDS_TYPE"
    NEEDS_CONVERSION = "NEEDS_CONVERSION"
    NEEDS_RANGE = "NEEDS_RANGE"
    NEEDS_INTERPRETATION = "NEEDS_INTERPRETATION"
    NEEDS_POLARITY = "NEEDS_POLARITY"
    NEEDS_SIGNAL_SELECTION = "NEEDS_SIGNAL_SELECTION"
    NEEDS_AGGREGATION = "NEEDS_AGGREGATION"
    NEEDS_LATCHING = "NEEDS_LATCHING"
    NEEDS_RECOVERY_SEMANTICS = "NEEDS_RECOVERY_SEMANTICS"
    NEEDS_SEVERITY = "NEEDS_SEVERITY"
    BLOCKED_BY_PHYSICAL_SOURCE = "BLOCKED_BY_PHYSICAL_SOURCE"


class CommissioningFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str | int | float | bool | dict[str, str] | tuple[str, ...] | None = None
    confidence: Confidence = Confidence.UNKNOWN
    approved: bool = False
    provenance: str = Field(min_length=1, max_length=512)
    note: str | None = Field(default=None, min_length=1, max_length=1024)

    @model_validator(mode="after")
    def approved_facts_have_values(self) -> "CommissioningFact":
        if self.approved and self.value is None:
            raise ValueError("an approved commissioning fact must have a value")
        return self

    @property
    def ready(self) -> bool:
        return self.approved and self.value is not None


def _unresolved_fact() -> CommissioningFact:
    return CommissioningFact(
        value=None,
        confidence=Confidence.UNKNOWN,
        approved=False,
        provenance="Unresolved commissioning input.",
    )


class CandidateSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    address: str | None = Field(default=None, min_length=1, max_length=128)
    symbol: str | None = Field(default=None, min_length=1, max_length=256)
    data_type: str | None = Field(default=None, min_length=1, max_length=128)
    native_unit: str | None = Field(default=None, min_length=1, max_length=64)
    role: str = Field(min_length=1, max_length=256)
    confidence: Confidence
    note: str = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def candidate_has_identity(self) -> "CandidateSource":
        if self.address is None and self.symbol is None:
            raise ValueError("a candidate source requires an address or symbol")
        return self


class CommissioningField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    equipment: str = Field(min_length=1, max_length=64)
    field: str = Field(min_length=1, max_length=64)
    logical_signal: str = Field(min_length=1, max_length=128)
    contract_kind: Literal["state", "readback", "condition", "alarm"]
    hmi_unit: str | None = Field(default=None, min_length=1, max_length=32)
    physical_source_status: PhysicalSourceStatus
    requirements: frozenset[Requirement]
    node_id: CommissioningFact
    plc_source: CommissioningFact = Field(default_factory=_unresolved_fact)
    plc_type: CommissioningFact = Field(default_factory=_unresolved_fact)
    native_unit: CommissioningFact = Field(default_factory=_unresolved_fact)
    conversion: CommissioningFact = Field(default_factory=_unresolved_fact)
    engineering_range: CommissioningFact = Field(default_factory=_unresolved_fact)
    interpretation: CommissioningFact = Field(default_factory=_unresolved_fact)
    polarity: CommissioningFact = Field(default_factory=_unresolved_fact)
    signal_selection: CommissioningFact = Field(default_factory=_unresolved_fact)
    aggregation: CommissioningFact = Field(default_factory=_unresolved_fact)
    latching: CommissioningFact = Field(default_factory=_unresolved_fact)
    recovery: CommissioningFact = Field(default_factory=_unresolved_fact)
    severity: CommissioningFact = Field(default_factory=_unresolved_fact)
    candidates: tuple[CandidateSource, ...] = ()
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def reject_test_node_ids(self) -> "CommissioningField":
        value = self.node_id.value
        if value is not None:
            if not isinstance(value, str):
                raise ValueError("a commissioning NodeId must be a string or null")
            normalized = value.upper()
            if any(
                marker in normalized
                for marker in (
                    "TESTONLY",
                    "TEST_ONLY",
                    "TODO",
                    "REPLACE_ME",
                    "CONFIGURE_ME",
                    "PLACEHOLDER",
                )
            ):
                raise ValueError("test or placeholder NodeIds are forbidden")
            if self.node_id.approved and not (
                ";" in value or value.startswith("i=") or value.startswith("s=")
            ):
                raise ValueError("approved NodeIds must use an OPC UA NodeId string")
        return self


class CommonParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128)
    fact: CommissioningFact


class ControllerMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vendor: CommissioningFact
    model: CommissioningFact
    runtime: CommissioningFact


EXPECTED_FIELDS = {
    ("cmps", "state"): "cmps.state",
    ("cmps", "current"): "cmps.current",
    ("cmps", "interlock"): "interlock.cmps",
    ("cfps", "state"): "cfps.state",
    ("cfps", "power"): "cfps.power",
    ("cfps", "feedback"): "cfps.feedback",
    ("cfps", "interlock"): "interlock.cfps",
    ("ipps", "state"): "ipps.state",
    ("ipps", "voltage"): "ipps.voltage",
    ("ipps", "current"): "ipps.current",
    ("ipps", "interlock"): "interlock.ipps",
    ("arc_detector", "state"): "alarm.arc_detector",
    ("ahvps", "state"): "ahvps.state",
    ("ahvps", "voltage"): "ahvps.voltage",
    ("ahvps", "protection"): "ahvps.protection",
    ("ahvps", "interlock"): "interlock.ahvps",
    ("chvps", "state"): "chvps.state",
    ("chvps", "voltage"): "chvps.voltage",
    ("chvps", "protection"): "chvps.protection",
    ("chvps", "interlock"): "interlock.chvps",
    ("pulse_generator", "state"): "pulse_generator.state",
    ("pulse_generator", "feedback"): "pulse_generator.feedback",
    ("pulse_generator", "pulse_length"): "pulse_generator.length",
    ("pulse_generator", "pulse_period"): "pulse_generator.period",
}

EXPECTED_HMI_UNITS = {
    ("cmps", "current"): "A",
    ("cfps", "power"): "W",
    ("ipps", "voltage"): "V",
    ("ipps", "current"): "A",
    ("ahvps", "voltage"): "kV",
    ("chvps", "voltage"): "kV",
    ("pulse_generator", "pulse_length"): "ms",
    ("pulse_generator", "pulse_period"): "s",
}

EXPECTED_REQUIREMENTS = {
    ("cmps", "state"): {Requirement.NODE_ID, Requirement.TYPE, Requirement.INTERPRETATION},
    ("cmps", "current"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
    },
    ("cmps", "interlock"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.POLARITY,
    },
    ("cfps", "state"): {Requirement.NODE_ID, Requirement.TYPE, Requirement.INTERPRETATION},
    ("cfps", "power"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
    },
    ("cfps", "feedback"): {Requirement.NODE_ID, Requirement.TYPE, Requirement.INTERPRETATION},
    ("cfps", "interlock"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.POLARITY,
    },
    ("ipps", "state"): {Requirement.NODE_ID, Requirement.TYPE, Requirement.INTERPRETATION},
    ("ipps", "voltage"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
        Requirement.SIGNAL_SELECTION,
    },
    ("ipps", "current"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
        Requirement.SIGNAL_SELECTION,
    },
    ("ipps", "interlock"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.POLARITY,
    },
    ("arc_detector", "state"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.POLARITY,
        Requirement.SIGNAL_SELECTION,
        Requirement.AGGREGATION,
        Requirement.LATCHING,
        Requirement.RECOVERY,
        Requirement.SEVERITY,
    },
    ("ahvps", "state"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.SIGNAL_SELECTION,
    },
    ("ahvps", "voltage"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
    },
    ("ahvps", "protection"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.POLARITY,
        Requirement.SIGNAL_SELECTION,
        Requirement.AGGREGATION,
    },
    ("ahvps", "interlock"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.POLARITY,
    },
    ("chvps", "state"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.SIGNAL_SELECTION,
    },
    ("chvps", "voltage"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
        Requirement.POLARITY,
    },
    ("chvps", "protection"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.POLARITY,
        Requirement.SIGNAL_SELECTION,
        Requirement.AGGREGATION,
    },
    ("chvps", "interlock"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.POLARITY,
    },
    ("pulse_generator", "state"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
    },
    ("pulse_generator", "feedback"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
    },
    ("pulse_generator", "pulse_length"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
    },
    ("pulse_generator", "pulse_period"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
    },
}

EXPECTED_COMMON_PARAMETERS = frozenset(
    {
        "endpoint",
        "namespace_indexes",
        "namespace_uris",
        "node_id_style",
        "security_policy",
        "trusted_server_certificate_identity",
        "authentication_method",
        "dedicated_read_only_account",
        "source_timestamp_behavior",
        "engineering_unit_metadata",
    }
)


class ProductionCommissioningTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    purpose: Literal["production-template"]
    status: Literal["incomplete", "under-review", "complete"]
    warning: str = Field(min_length=1, max_length=512)
    controller: ControllerMetadata
    common_opcua: tuple[CommonParameter, ...]
    fields: tuple[CommissioningField, ...]

    @model_validator(mode="after")
    def validate_complete_contract_shape(self) -> "ProductionCommissioningTemplate":
        actual = {(item.equipment, item.field): item.logical_signal for item in self.fields}
        if actual != EXPECTED_FIELDS:
            missing = sorted(set(EXPECTED_FIELDS).difference(actual))
            extra = sorted(set(actual).difference(EXPECTED_FIELDS))
            mismatched = sorted(
                key
                for key in set(actual).intersection(EXPECTED_FIELDS)
                if actual[key] != EXPECTED_FIELDS[key]
            )
            raise ValueError(
                f"equipment contract mismatch (missing={missing}, extra={extra}, "
                f"mismatched={mismatched})"
            )
        for key, expected_unit in EXPECTED_HMI_UNITS.items():
            item = next(field for field in self.fields if (field.equipment, field.field) == key)
            if item.hmi_unit != expected_unit:
                raise ValueError(f"{item.logical_signal} must use HMI unit {expected_unit}")
        for item in self.fields:
            key = (item.equipment, item.field)
            if item.requirements != EXPECTED_REQUIREMENTS[key]:
                raise ValueError(
                    f"{item.logical_signal} readiness requirements do not match the "
                    "authoritative software contract"
                )
        populated_node_ids = [
            item.node_id.value for item in self.fields if item.node_id.value is not None
        ]
        if len(populated_node_ids) != len(set(populated_node_ids)):
            raise ValueError("commissioning NodeIds must be unique")
        common_names = {item.name for item in self.common_opcua}
        if common_names != EXPECTED_COMMON_PARAMETERS:
            raise ValueError("common OPC UA commissioning parameters are incomplete")
        return self


REQUIREMENT_BLOCKERS = {
    Requirement.NODE_ID: ("node_id", ReadinessBlocker.NEEDS_NODE_ID),
    Requirement.TYPE: ("plc_type", ReadinessBlocker.NEEDS_TYPE),
    Requirement.CONVERSION: ("conversion", ReadinessBlocker.NEEDS_CONVERSION),
    Requirement.RANGE: ("engineering_range", ReadinessBlocker.NEEDS_RANGE),
    Requirement.INTERPRETATION: (
        "interpretation",
        ReadinessBlocker.NEEDS_INTERPRETATION,
    ),
    Requirement.POLARITY: ("polarity", ReadinessBlocker.NEEDS_POLARITY),
    Requirement.SIGNAL_SELECTION: (
        "signal_selection",
        ReadinessBlocker.NEEDS_SIGNAL_SELECTION,
    ),
    Requirement.AGGREGATION: ("aggregation", ReadinessBlocker.NEEDS_AGGREGATION),
    Requirement.LATCHING: ("latching", ReadinessBlocker.NEEDS_LATCHING),
    Requirement.RECOVERY: ("recovery", ReadinessBlocker.NEEDS_RECOVERY_SEMANTICS),
    Requirement.SEVERITY: ("severity", ReadinessBlocker.NEEDS_SEVERITY),
}


class FieldReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    equipment: str
    field: str
    logical_signal: str
    blockers: tuple[ReadinessBlocker, ...]


class CommissioningReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    production_ready: bool
    fields: tuple[FieldReadiness, ...]
    common_missing: tuple[str, ...]


def load_commissioning_template(path: Path) -> ProductionCommissioningTemplate:
    try:
        return ProductionCommissioningTemplate.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError) as exc:
        raise CommissioningTemplateError(
            f"Invalid OPC UA production commissioning template: {path.name}"
        ) from exc


def field_readiness(field: CommissioningField) -> FieldReadiness:
    blockers: list[ReadinessBlocker] = []
    if field.physical_source_status == PhysicalSourceStatus.NOT_RECOVERED:
        blockers.append(ReadinessBlocker.BLOCKED_BY_PHYSICAL_SOURCE)
    for requirement in Requirement:
        if requirement not in field.requirements:
            continue
        fact_name, blocker = REQUIREMENT_BLOCKERS[requirement]
        if not getattr(field, fact_name).ready:
            blockers.append(blocker)
    return FieldReadiness(
        equipment=field.equipment,
        field=field.field,
        logical_signal=field.logical_signal,
        blockers=tuple(blockers),
    )


def readiness_report(
    template: ProductionCommissioningTemplate,
) -> CommissioningReadiness:
    fields = tuple(field_readiness(field) for field in template.fields)
    common_missing = tuple(
        parameter.name for parameter in template.common_opcua if not parameter.fact.ready
    )
    return CommissioningReadiness(
        production_ready=(
            template.status == "complete"
            and not common_missing
            and all(not field.blockers for field in fields)
        ),
        fields=fields,
        common_missing=common_missing,
    )


def format_readiness_report(
    template: ProductionCommissioningTemplate,
    report: CommissioningReadiness,
) -> str:
    lines = [
        "OPC UA production commissioning readiness",
        f"purpose = {template.purpose}",
        f"template_status = {template.status}",
        f"production_ready = {str(report.production_ready).lower()}",
        "",
    ]
    current_equipment = None
    for item in report.fields:
        if item.equipment != current_equipment:
            current_equipment = item.equipment
            lines.extend((current_equipment.upper(),))
        blockers = item.blockers or ("READY",)
        lines.append(f"  {item.field} ({item.logical_signal})")
        lines.extend(f"    {blocker.value if isinstance(blocker, Enum) else blocker}" for blocker in blockers)
    lines.extend(("", "COMMON OPC UA CONFIGURATION"))
    if report.common_missing:
        lines.extend(f"  UNRESOLVED: {name}" for name in report.common_missing)
    else:
        lines.append("  READY")
    return "\n".join(lines)


def _fact_text(fact: CommissioningFact) -> str:
    if fact.value is None:
        return "TBD"
    if isinstance(fact.value, dict):
        return "; ".join(f"{key}={value}" for key, value in fact.value.items())
    if isinstance(fact.value, tuple):
        return "; ".join(fact.value)
    return str(fact.value)


def _candidate_text(field: CommissioningField) -> str:
    if not field.candidates:
        return _fact_text(field.plc_source)
    rendered = []
    for item in field.candidates:
        identity = " / ".join(part for part in (item.address, item.symbol) if part)
        technical = ", ".join(
            part for part in (item.data_type, item.native_unit) if part
        )
        suffix = f"; {technical}" if technical else ""
        rendered.append(f"{identity} ({item.role}{suffix})")
    return "<br>".join(rendered)


def render_commissioning_matrix(
    template: ProductionCommissioningTemplate,
) -> str:
    report = readiness_report(template)
    rows = []
    readiness_by_key = {
        (item.equipment, item.field): item for item in report.fields
    }
    for field in template.fields:
        readiness = readiness_by_key[(field.equipment, field.field)]
        missing = ", ".join(blocker.value for blocker in readiness.blockers) or "READY"
        rows.append(
            "| "
            + " | ".join(
                (
                    field.equipment.upper(),
                    field.field,
                    _candidate_text(field),
                    _fact_text(field.node_id),
                    _fact_text(field.plc_type),
                    _fact_text(field.native_unit),
                    field.hmi_unit or "NOT APPLICABLE",
                    _fact_text(field.conversion),
                    _fact_text(field.interpretation),
                    min(
                        (candidate.confidence for candidate in field.candidates),
                        default=field.plc_source.confidence,
                        key=lambda confidence: list(Confidence).index(confidence),
                    ).value.upper(),
                    missing,
                )
            )
            + " |"
        )
    return "\n".join(
        (
            "# OPC UA production commissioning matrix",
            "",
            "> **THIS IS NOT A PRODUCTION NODE MAP.** It is non-executable commissioning preparation. Every candidate requires explicit verification and approval before being copied into a separately validated runtime production map.",
            "",
            f"- Template purpose: `{template.purpose}`",
            f"- Template status: `{template.status}`",
            f"- Production ready: `{str(report.production_ready).lower()}`",
            "- Runtime boundary: `APP_MODE=opcua_readonly` accepts only the independent strict `NodeMap` schema with `purpose=production`.",
            "",
            "| Equipment | Field | PLC candidate | NodeId | PLC type | Native unit | HMI unit | Conversion | Interpretation | Confidence | Missing |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
            *rows,
            "",
            "## Common OPC UA configuration",
            "",
            "All entries below remain unresolved and require controls-engineering approval. Non-local production OPC UA must use `SignAndEncrypt`; this document does not select a SecurityPolicy.",
            "",
            "| Parameter | Value | Confidence | Approval | Note |",
            "|---|---|---|---|---|",
            *(
                f"| {item.name} | {_fact_text(item.fact)} | {item.fact.confidence.value.upper()} | {'APPROVED' if item.fact.approved else 'UNAPPROVED'} | {item.fact.note or item.fact.provenance} |"
                for item in template.common_opcua
            ),
            "",
            "## Commissioning rules",
            "",
            "- `STRONGLY_INFERRED` and `WEAKLY_INFERRED` are never production approval.",
            "- Setpoint outputs `%QW27`, `%QW24`, and `%QW26` are command-side context only and must not be used as actual readbacks.",
            "- The CFPS voltage-to-power relationship is unresolved and non-linear; no guessed W/V conversion is permitted.",
            "- Raw versus converted IPPS symbols must be selected only after inspecting the CODESYS OPC UA Symbol Configuration and verifying the 750-471 process-image mode.",
            "- Arc aggregation, polarity, latching, recovery, and severity remain unresolved.",
            "",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OPC UA commissioning template tools")
    parser.add_argument("action", choices=("report", "validate", "matrix"))
    parser.add_argument("template", type=Path)
    args = parser.parse_args(argv)
    try:
        template = load_commissioning_template(args.template)
    except CommissioningTemplateError as exc:
        print(exc)
        return 2
    report = readiness_report(template)
    if args.action == "matrix":
        print(render_commissioning_matrix(template))
    else:
        print(format_readiness_report(template, report))
    if args.action == "validate" and not report.production_ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
