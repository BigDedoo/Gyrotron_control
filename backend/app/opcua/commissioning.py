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
    PLC_SOURCE_CONFIRMED = "plc_source_confirmed"
    NEEDS_CONTROLS_VERIFICATION = "needs_controls_verification"
    MISSING_PHYSICAL_SOURCE = "missing_physical_source"
    UNKNOWN = "unknown"


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
    FIELD_SELECTION = "field_selection"
    PROCESS_IMAGE_REPRESENTATION = "process_image_representation"


class ReadinessBlocker(str, Enum):
    NEEDS_NODE_ID_DISCOVERY = "NEEDS_NODE_ID_DISCOVERY"
    NEEDS_TYPE = "NEEDS_TYPE"
    NEEDS_CONVERSION = "NEEDS_CONVERSION"
    NEEDS_RANGE_APPROVAL = "NEEDS_RANGE_APPROVAL"
    NEEDS_INTERPRETATION = "NEEDS_INTERPRETATION"
    NEEDS_POLARITY_VERIFICATION = "NEEDS_POLARITY_VERIFICATION"
    NEEDS_SIGNAL_SELECTION = "NEEDS_SIGNAL_SELECTION"
    NEEDS_CONTROLS_APPROVAL_FOR_FIELD_SELECTION = (
        "NEEDS_CONTROLS_APPROVAL_FOR_FIELD_SELECTION"
    )
    NEEDS_AGGREGATION = "NEEDS_AGGREGATION"
    NEEDS_LATCHING = "NEEDS_LATCHING"
    NEEDS_RECOVERY_SEMANTICS = "NEEDS_RECOVERY_SEMANTICS"
    NEEDS_SEVERITY_APPROVAL = "NEEDS_SEVERITY_APPROVAL"
    NEEDS_CONTROLS_VERIFICATION = "NEEDS_CONTROLS_VERIFICATION"
    NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION = (
        "NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION"
    )


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
    raw_symbol: str | None = Field(default=None, min_length=1, max_length=256)
    data_type: str | None = Field(default=None, min_length=1, max_length=128)
    native_unit: str | None = Field(default=None, min_length=1, max_length=64)
    role: str = Field(min_length=1, max_length=256)
    confidence: Confidence
    note: str = Field(min_length=1, max_length=1024)

    @model_validator(mode="after")
    def candidate_has_identity(self) -> "CandidateSource":
        if self.address is None and self.symbol is None and self.raw_symbol is None:
            raise ValueError("a candidate source requires an address or PLC symbol")
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
    field_selection: CommissioningFact = Field(default_factory=_unresolved_fact)
    exported_symbol_path: CommissioningFact = Field(default_factory=_unresolved_fact)
    symbol_config_access: CommissioningFact = Field(default_factory=_unresolved_fact)
    electrical_input_mode: CommissioningFact = Field(default_factory=_unresolved_fact)
    process_image_representation: CommissioningFact = Field(default_factory=_unresolved_fact)
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
        if self.physical_source_status == PhysicalSourceStatus.PLC_SOURCE_CONFIRMED:
            if not self.plc_source.ready or self.plc_source.confidence != Confidence.CONFIRMED:
                raise ValueError(
                    "PLC_SOURCE_CONFIRMED requires an approved, confirmed PLC source"
                )
        if (
            self.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
            and self.plc_source.value is not None
        ):
            raise ValueError(
                "MISSING_PHYSICAL_SOURCE cannot declare a current PLC source"
            )
        if self.exported_symbol_path.value is not None:
            if not self.exported_symbol_path.ready:
                raise ValueError("an exported symbol path must be approved")
            if self.exported_symbol_path.confidence != Confidence.CONFIRMED:
                raise ValueError("an exported symbol path must be confirmed")
            if self.symbol_config_access.value not in {"Read", "ReadWrite"}:
                raise ValueError("an exported symbol requires Read or ReadWrite access")
            if not self.symbol_config_access.ready:
                raise ValueError("exported symbol access must be approved")
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
    runtime_version: CommissioningFact
    opcua_server_version: CommissioningFact


class SymbolConfigurationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project: CommissioningFact
    device: CommissioningFact
    application: CommissioningFact
    schema_header_version: CommissioningFact
    symbol_config_object_version: CommissioningFact
    runtimeid: CommissioningFact
    compiler: CommissioningFact
    lmm: CommissioningFact
    profile: CommissioningFact
    libversion: CommissioningFact
    support_opcua: CommissioningFact
    read_exports: tuple[str, ...]
    readwrite_exports: tuple[str, ...]
    security_note: str = Field(min_length=1, max_length=2048)


class ForbiddenSubstitute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    application_field: str = Field(min_length=1, max_length=128)
    physical_address: str | None = Field(default=None, min_length=1, max_length=128)
    plc_symbol: str = Field(min_length=1, max_length=256)
    reason: str = Field(min_length=1, max_length=1024)
    confidence: Literal[Confidence.CONFIRMED]


class EquipmentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    application_equipment: Literal["AHVPS", "CHVPS"]
    plc_equipment: Literal["APS", "CPS"]
    meaning: str = Field(min_length=1, max_length=128)
    confidence: Confidence
    approved: bool = False
    provenance: str = Field(min_length=1, max_length=512)


class GlobalCommissioningIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Literal[
        "750_471_process_representation",
        "poor_vacuum_polarity",
        "cfps_stabilization_polarity",
    ]
    blocker: ReadinessBlocker
    affected_signals: tuple[str, ...]
    resolution: CommissioningFact
    evidence: tuple[str, ...]


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
    ("cfps", "feedback"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.INTERPRETATION,
        Requirement.FIELD_SELECTION,
    },
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
        Requirement.PROCESS_IMAGE_REPRESENTATION,
    },
    ("ipps", "current"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
        Requirement.PROCESS_IMAGE_REPRESENTATION,
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
    },
    ("ahvps", "voltage"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
    },
    ("ahvps", "protection"): {Requirement.NODE_ID, Requirement.TYPE, Requirement.INTERPRETATION},
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
    },
    ("chvps", "voltage"): {
        Requirement.NODE_ID,
        Requirement.TYPE,
        Requirement.CONVERSION,
        Requirement.RANGE,
        Requirement.POLARITY,
    },
    ("chvps", "protection"): {Requirement.NODE_ID, Requirement.TYPE, Requirement.INTERPRETATION},
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

    schema_version: Literal[3]
    purpose: Literal["production-template"]
    status: Literal["incomplete", "under-review", "complete"]
    warning: str = Field(min_length=1, max_length=512)
    controller: ControllerMetadata
    symbol_configuration: SymbolConfigurationMetadata
    equipment_identities: tuple[EquipmentIdentity, ...]
    global_issues: tuple[GlobalCommissioningIssue, ...]
    forbidden_substitutes: tuple[ForbiddenSubstitute, ...]
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
        identities = {
            (item.application_equipment, item.plc_equipment)
            for item in self.equipment_identities
        }
        if identities != {("AHVPS", "APS"), ("CHVPS", "CPS")}:
            raise ValueError("equipment identity evidence is incomplete")
        issue_names = {item.name for item in self.global_issues}
        if issue_names != {
            "750_471_process_representation",
            "poor_vacuum_polarity",
            "cfps_stabilization_polarity",
        }:
            raise ValueError("global commissioning issues are incomplete")
        expected_substitutes = {
            "cfps.power",
            "chvps.voltage",
            "ahvps.voltage",
            "pulse_generator.length",
            "ipps.hv_active",
        }
        if {item.application_field for item in self.forbidden_substitutes} != expected_substitutes:
            raise ValueError("forbidden readback substitutes are incomplete")
        return self


REQUIREMENT_BLOCKERS = {
    Requirement.NODE_ID: ("node_id", ReadinessBlocker.NEEDS_NODE_ID_DISCOVERY),
    Requirement.TYPE: ("plc_type", ReadinessBlocker.NEEDS_TYPE),
    Requirement.CONVERSION: ("conversion", ReadinessBlocker.NEEDS_CONVERSION),
    Requirement.RANGE: ("engineering_range", ReadinessBlocker.NEEDS_RANGE_APPROVAL),
    Requirement.INTERPRETATION: (
        "interpretation",
        ReadinessBlocker.NEEDS_INTERPRETATION,
    ),
    Requirement.POLARITY: ("polarity", ReadinessBlocker.NEEDS_POLARITY_VERIFICATION),
    Requirement.SIGNAL_SELECTION: (
        "signal_selection",
        ReadinessBlocker.NEEDS_SIGNAL_SELECTION,
    ),
    Requirement.AGGREGATION: ("aggregation", ReadinessBlocker.NEEDS_AGGREGATION),
    Requirement.LATCHING: ("latching", ReadinessBlocker.NEEDS_LATCHING),
    Requirement.RECOVERY: ("recovery", ReadinessBlocker.NEEDS_RECOVERY_SEMANTICS),
    Requirement.SEVERITY: ("severity", ReadinessBlocker.NEEDS_SEVERITY_APPROVAL),
    Requirement.FIELD_SELECTION: (
        "field_selection",
        ReadinessBlocker.NEEDS_CONTROLS_APPROVAL_FOR_FIELD_SELECTION,
    ),
    Requirement.PROCESS_IMAGE_REPRESENTATION: (
        "process_image_representation",
        ReadinessBlocker.NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION,
    ),
}


class FieldReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    equipment: str
    field: str
    logical_signal: str
    source_status: PhysicalSourceStatus
    exported_symbol_confirmed: bool
    blockers: tuple[ReadinessBlocker, ...]


class ReadinessCounts(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plc_source_confirmed: int
    partially_resolved: int
    missing_physical_source: int
    exported_symbol_confirmed: int
    needs_opcua_discovery: int


class CommissioningReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    production_ready: bool
    fields: tuple[FieldReadiness, ...]
    common_missing: tuple[str, ...]
    global_blockers: tuple[ReadinessBlocker, ...]
    counts: ReadinessCounts


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
    source_status = field.physical_source_status
    if source_status not in {
        PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE,
        PhysicalSourceStatus.UNKNOWN,
    }:
        for requirement in Requirement:
            if requirement not in field.requirements:
                continue
            fact_name, blocker = REQUIREMENT_BLOCKERS[requirement]
            if getattr(field, fact_name).ready:
                continue
            if (
                source_status == PhysicalSourceStatus.NEEDS_CONTROLS_VERIFICATION
                and requirement
                in {Requirement.TYPE, Requirement.INTERPRETATION, Requirement.POLARITY}
            ):
                continue
            blockers.append(blocker)
    return FieldReadiness(
        equipment=field.equipment,
        field=field.field,
        logical_signal=field.logical_signal,
        source_status=source_status,
        exported_symbol_confirmed=field.exported_symbol_path.ready,
        blockers=tuple(blockers),
    )


def readiness_report(
    template: ProductionCommissioningTemplate,
) -> CommissioningReadiness:
    fields = tuple(field_readiness(field) for field in template.fields)
    common_missing = tuple(
        parameter.name for parameter in template.common_opcua if not parameter.fact.ready
    )
    global_blockers = tuple(
        issue.blocker for issue in template.global_issues if not issue.resolution.ready
    )
    counts = ReadinessCounts(
        plc_source_confirmed=sum(
            field.source_status == PhysicalSourceStatus.PLC_SOURCE_CONFIRMED
            for field in fields
        ),
        partially_resolved=sum(
            field.source_status == PhysicalSourceStatus.NEEDS_CONTROLS_VERIFICATION
            for field in fields
        ),
        missing_physical_source=sum(
            field.source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
            for field in fields
        ),
        exported_symbol_confirmed=sum(field.exported_symbol_confirmed for field in fields),
        needs_opcua_discovery=sum(
            ReadinessBlocker.NEEDS_NODE_ID_DISCOVERY in field.blockers for field in fields
        ),
    )
    return CommissioningReadiness(
        production_ready=(
            template.status == "complete"
            and not common_missing
            and not global_blockers
            and all(not field.blockers for field in fields)
            and all(
                field.source_status == PhysicalSourceStatus.PLC_SOURCE_CONFIRMED
                for field in fields
            )
            and all(
                identity.approved and identity.confidence == Confidence.CONFIRMED
                for identity in template.equipment_identities
            )
        ),
        fields=fields,
        common_missing=common_missing,
        global_blockers=global_blockers,
        counts=counts,
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
        "SUMMARY",
        f"  PLC source confirmed: {report.counts.plc_source_confirmed}",
        f"  Partially resolved: {report.counts.partially_resolved}",
        f"  Missing physical source: {report.counts.missing_physical_source}",
        f"  Exported symbol confirmed: {report.counts.exported_symbol_confirmed}",
        f"  Needs OPC UA discovery: {report.counts.needs_opcua_discovery}",
        "",
    ]
    current_equipment = None
    for item in report.fields:
        if item.equipment != current_equipment:
            current_equipment = item.equipment
            lines.extend((current_equipment.upper(),))
        lines.append(f"  {item.field} ({item.logical_signal})")
        lines.append(f"    {item.source_status.value.upper()}")
        if item.exported_symbol_confirmed:
            lines.append("    EXPORTED_SYMBOL_CONFIRMED")
        lines.extend(f"    {blocker.value}" for blocker in item.blockers)
    lines.extend(("", "COMMON OPC UA CONFIGURATION"))
    if report.common_missing:
        lines.extend(f"  UNRESOLVED: {name}" for name in report.common_missing)
    else:
        lines.append("  READY")
    lines.extend(("", "GLOBAL COMMISSIONING ISSUES"))
    if report.global_blockers:
        lines.extend(f"  {blocker.value}" for blocker in report.global_blockers)
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


def _candidate_column(field: CommissioningField, attribute: str) -> str:
    rendered = [
        f"{value} ({candidate.role})"
        for candidate in field.candidates
        if (value := getattr(candidate, attribute)) is not None
    ]
    if field.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE:
        if rendered:
            return "NOT PRESENT IN CURRENT PLC; related context only: " + "<br>".join(
                rendered
            )
        return "NOT PRESENT IN CURRENT PLC"
    if rendered:
        return "<br>".join(rendered)
    return "UNKNOWN"


def _source_confidence(field: CommissioningField) -> str:
    if field.physical_source_status in {
        PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE,
        PhysicalSourceStatus.UNKNOWN,
    }:
        return Confidence.UNKNOWN.value.upper()
    return field.plc_source.confidence.value.upper()


def _opcua_discovery_status(field: CommissioningField) -> str:
    if field.node_id.ready:
        return "DISCOVERED AND APPROVED"
    if field.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE:
        return "NOT APPLICABLE UNTIL SOURCE EXISTS"
    if field.physical_source_status == PhysicalSourceStatus.UNKNOWN:
        return "UNKNOWN"
    return ReadinessBlocker.NEEDS_NODE_ID_DISCOVERY.value


def _matrix_blockers(readiness: FieldReadiness) -> str:
    values = [blocker.value for blocker in readiness.blockers]
    if readiness.source_status != PhysicalSourceStatus.PLC_SOURCE_CONFIRMED:
        values.insert(0, readiness.source_status.value.upper())
    return ", ".join(dict.fromkeys(values)) or "NONE"


def _plc_variable_column(field: CommissioningField) -> str:
    values: list[str] = []
    for candidate in field.candidates:
        for value in (candidate.raw_symbol, candidate.symbol):
            if value and value not in values:
                values.append(value)
    if values:
        return "<br>".join(values)
    if field.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE:
        return "NOT PRESENT IN CURRENT PLC"
    return "UNKNOWN"


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
        conversion = _fact_text(field.conversion)
        if field.conversion.value is None:
            conversion = (
                "UNKNOWN" if field.contract_kind == "readback" else "NOT APPLICABLE"
            )
        exported_path = "UNKNOWN"
        if field.exported_symbol_path.value is not None:
            exported_path = _fact_text(field.exported_symbol_path)
        elif field.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE:
            exported_path = "NOT PRESENT IN CURRENT PLC"
        rows.append(
            "| "
            + " | ".join(
                (
                    field.equipment.upper(),
                    field.field,
                    _candidate_column(field, "address"),
                    _plc_variable_column(field),
                    exported_path,
                    "YES" if field.exported_symbol_path.ready else "NO",
                    _fact_text(field.symbol_config_access)
                    if field.symbol_config_access.value is not None
                    else "NOT APPLICABLE",
                    _fact_text(field.plc_type)
                    if field.plc_type.value is not None
                    else "UNKNOWN",
                    _fact_text(field.native_unit) if field.native_unit.value is not None else "UNKNOWN",
                    field.hmi_unit or "NOT APPLICABLE",
                    conversion,
                    _source_confidence(field),
                    _opcua_discovery_status(field),
                    _matrix_blockers(readiness),
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
            f"- PLC source confirmed: `{report.counts.plc_source_confirmed}`",
            f"- Partially resolved: `{report.counts.partially_resolved}`",
            f"- Missing physical source: `{report.counts.missing_physical_source}`",
            f"- Exported symbol confirmed: `{report.counts.exported_symbol_confirmed}`",
            f"- Needs OPC UA discovery: `{report.counts.needs_opcua_discovery}`",
            "- Runtime boundary: `APP_MODE=opcua_readonly` accepts only the independent strict `NodeMap` schema with `purpose=production`.",
            "",
            "| Equipment | HMI field | Physical PLC source | PLC variable | Exported CODESYS symbol path | Exported? | Symbol access | Expected datatype | Native unit | HMI unit | Conversion | Confidence | NodeId discovered? | Remaining blockers |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
            *rows,
            "",
            "## Confirmed equipment identities",
            "",
            "| Application equipment | PLC equipment | Meaning | Confidence | Approval | Provenance |",
            "|---|---|---|---|---|---|",
            *(
                f"| {item.application_equipment} | {item.plc_equipment} | {item.meaning} | {item.confidence.value.upper()} | {'APPROVED' if item.approved else 'UNAPPROVED'} | {item.provenance} |"
                for item in template.equipment_identities
            ),
            "",
            "## Global commissioning issues",
            "",
            "| Issue | Blocker | Affected signals | Resolution | Evidence |",
            "|---|---|---|---|---|",
            *(
                f"| {item.name} | {item.blocker.value} | {', '.join(item.affected_signals)} | {_fact_text(item.resolution)} | {'<br>'.join(item.evidence)} |"
                for item in template.global_issues
            ),
            "",
            "## Confirmed forbidden substitutes",
            "",
            "| Application field | Physical address | PLC / exported symbol | Reason | Confidence |",
            "|---|---|---|---|---|",
            *(
                f"| {item.application_field} | {item.physical_address or 'NOT APPLICABLE'} | {item.plc_symbol} | {item.reason} | {item.confidence.value.upper()} |"
                for item in template.forbidden_substitutes
            ),
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
            "- The exported processed IPPS REAL symbols are selected; exact 750-471 WORD process representation still requires verification of the PLC engineering conversion.",
            "- Arc aggregation, polarity, latching, recovery, and severity remain unresolved.",
            "- Poor-vacuum physical polarity remains unresolved; current PLC logic must not be changed by this metadata task.",
        )
    )


def render_nodeid_discovery_plan(template: ProductionCommissioningTemplate) -> str:
    """Render the next offline commissioning step without importing a network client."""
    report = readiness_report(template)
    readiness_by_key = {(item.equipment, item.field): item for item in report.fields}
    exported_fields = tuple(field for field in template.fields if field.exported_symbol_path.ready)
    rows = []
    for field in exported_fields:
        readiness = readiness_by_key[(field.equipment, field.field)]
        blockers = ", ".join(blocker.value for blocker in readiness.blockers) or "NONE"
        rows.append(
            "| "
            + " | ".join(
                (
                    field.logical_signal,
                    str(field.exported_symbol_path.value),
                    _fact_text(field.plc_type),
                    _fact_text(field.symbol_config_access),
                    field.hmi_unit or "NOT APPLICABLE",
                    blockers,
                )
            )
            + " |"
        )
    return "\n".join(
        (
            "# Offline OPC UA NodeId discovery plan",
            "",
            "> This checklist is generated only from committed commissioning metadata. It makes no network calls, opens no socket, instantiates no OPC UA client, and contains no inferred NodeIds.",
            "",
            f"Preferred exported fields awaiting read-only discovery: **{len(exported_fields)}**",
            "",
            "| HMI field | Preferred exported CODESYS path | Expected datatype | Symbol config access | HMI unit | Remaining verification |",
            "|---|---|---|---|---|---|",
            *rows,
            "",
            "## Operator record for the later live browse",
            "",
            "For each row, record the Namespace URI, namespace index, exact NodeId, BrowseName, DataType, AccessLevel, UserAccessLevel, SourceTimestamp behavior, and engineering-unit metadata when present.",
            "",
            "The generated Symbol Configuration exposes command and setpoint symbols as `ReadWrite`. During the later browse, verify that the production application identity has effective `UserAccessLevel` read-only for telemetry and no write permission to command/setpoint symbols. Do not attempt writes as a test.",
            "",
            "Do not derive NodeIds from the exported paths. Record only exact values returned by the real server during the separately authorized read-only browse.",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OPC UA commissioning template tools")
    parser.add_argument("action", choices=("report", "validate", "matrix", "nodeid-plan"))
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
    elif args.action == "nodeid-plan":
        print(render_nodeid_discovery_plan(template))
    else:
        print(format_readiness_report(template, report))
    if args.action == "validate" and not report.production_ready:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
