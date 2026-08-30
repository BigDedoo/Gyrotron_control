import json
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.opcua.commissioning import (
    EXPECTED_FIELDS,
    CommissioningTemplateError,
    Confidence,
    PhysicalSourceStatus,
    ProductionCommissioningTemplate,
    ReadinessBlocker,
    load_commissioning_template,
    main,
    readiness_report,
    render_commissioning_matrix,
    render_nodeid_discovery_plan,
)
from app.opcua.node_map import NodeMapError, NodeMapping, load_node_map


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
TEMPLATE_PATH = BACKEND_ROOT / "config" / "opcua_nodes.production.template.json"
MATRIX_PATH = REPOSITORY_ROOT / "docs" / "opcua_production_commissioning.md"
PLAN_PATH = REPOSITORY_ROOT / "docs" / "opcua_nodeid_discovery.md"


@pytest.fixture(scope="module")
def template():
    return load_commissioning_template(TEMPLATE_PATH)


def _field(template, equipment: str, field: str):
    return next(
        item
        for item in template.fields
        if item.equipment == equipment and item.field == field
    )


def _blockers(template, equipment: str, field: str):
    return set(
        next(
            item
            for item in readiness_report(template).fields
            if item.equipment == equipment and item.field == field
        ).blockers
    )


def test_template_contract_is_complete_non_runnable_and_has_no_node_ids(template):
    actual = {(item.equipment, item.field): item.logical_signal for item in template.fields}
    report = readiness_report(template)

    assert template.schema_version == 3
    assert template.purpose == "production-template"
    assert template.status == "incomplete"
    assert actual == EXPECTED_FIELDS
    assert len(template.fields) == 24
    assert all(item.node_id.value is None for item in template.fields)
    assert report.production_ready is False
    assert report.counts.plc_source_confirmed == 14
    assert report.counts.partially_resolved == 2
    assert report.counts.missing_physical_source == 8
    assert report.counts.exported_symbol_confirmed == 15
    assert report.counts.needs_opcua_discovery == 16
    with pytest.raises(NodeMapError):
        load_node_map(TEMPLATE_PATH)
    with pytest.raises(ValidationError):
        NodeMapping(signal="cmps.current", node_id=None, expected_type="float", unit="A")


def test_changing_only_purpose_cannot_bypass_runtime_or_commissioning_schema(tmp_path):
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["purpose"] = "production"
    with pytest.raises(ValidationError):
        ProductionCommissioningTemplate.model_validate(payload)
    changed = tmp_path / "purpose-only.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(NodeMapError):
        load_node_map(changed)


def test_symbol_configuration_metadata_is_exact_and_server_version_unknown(template):
    symbols = template.symbol_configuration
    assert symbols.project.value == "Test_gyro"
    assert symbols.device.value == "Device"
    assert symbols.application.value == "Application"
    assert symbols.schema_header_version.value == "3.5.14.0"
    assert symbols.symbol_config_object_version.value == "4.6.1.0"
    assert symbols.runtimeid.value == "3.5.21.30"
    assert symbols.compiler.value == "3.5.21.30"
    assert symbols.lmm.value == "3.5.21.30"
    assert symbols.profile.value == "CODESYS V3.5 SP21 Patch 3+"
    assert symbols.libversion.value == "4.6.0.0"
    assert symbols.support_opcua.value is True
    assert symbols.support_opcua.confidence == Confidence.CONFIRMED
    assert template.controller.opcua_server_version.value is None


def test_readwrite_surface_is_documented_but_not_used_as_telemetry(template):
    readwrite = set(template.symbol_configuration.readwrite_exports)
    assert "Application.GVL_HMI.eCmd_APS" in readwrite
    assert "Application.GVL_HMI.xCmd_IPPS_Start" in readwrite
    assert "Application.GVL_Setpoints.rSp_AnodeVolt_V" in readwrite
    assert "Application.GVL_Setpoints.rSp_PulseDuration_V" in readwrite
    selected = {field.exported_symbol_path.value for field in template.fields}
    assert not selected.intersection(readwrite)
    assert "UserAccessLevel" in template.symbol_configuration.security_note
    assert "no writes" in template.symbol_configuration.security_note


@pytest.mark.parametrize(
    ("equipment", "field", "path"),
    (
        ("cmps", "state", "Application.GVL_IntS.gIntS_Inp.CMPS_On"),
        ("cmps", "interlock", "Application.GVL_IntS.gIntS_Outp.Auth_CMPS"),
        ("cfps", "state", "Application.GVL_IntS.gIntS_Inp.CFPS_On"),
        ("cfps", "feedback", "Application.PLC_PRG.filamentData.Sts_Run"),
        ("cfps", "interlock", "Application.GVL_IntS.gIntS_Outp.Auth_CFPS"),
        ("ipps", "state", "Application.GVL_IntS.gIntS_Inp.IPPS_On"),
        ("ipps", "voltage", "Application.PLC_PRG.daqData.IonPumpVoltage_kV"),
        ("ipps", "current", "Application.PLC_PRG.daqData.IonPumpCurrent_mA"),
        ("ipps", "interlock", "Application.GVL_IntS.gIntS_Outp.Auth_IPPS"),
        ("ahvps", "state", "Application.GVL_IntS.gIntS_Inp.APS_On"),
        ("ahvps", "protection", "Application.GVL_Alarms.gAlarms.ApsFault"),
        ("ahvps", "interlock", "Application.GVL_IntS.gIntS_Outp.Auth_APS"),
        ("chvps", "state", "Application.GVL_IntS.gIntS_Inp.CPS_On"),
        ("chvps", "protection", "Application.GVL_Alarms.gAlarms.CpsFault"),
        ("chvps", "interlock", "Application.GVL_IntS.gIntS_Outp.Auth_CPS"),
    ),
)
def test_preferred_exported_paths_are_confirmed_read_only(template, equipment, field, path):
    item = _field(template, equipment, field)
    assert item.exported_symbol_path.value == path
    assert item.exported_symbol_path.confidence == Confidence.CONFIRMED
    assert item.exported_symbol_path.approved is True
    assert item.symbol_config_access.value == "Read"
    assert item.node_id.value is None


def test_cmps_current_remains_missing(template):
    current = _field(template, "cmps", "current")
    assert current.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
    assert current.exported_symbol_path.value is None


def test_cfps_run_feedback_selection_and_stabilization_are_precise(template):
    feedback = _field(template, "cfps", "feedback")
    assert feedback.physical_source_status == PhysicalSourceStatus.NEEDS_CONTROLS_VERIFICATION
    assert feedback.plc_source.value == "filamentData.Sts_Run"
    assert feedback.plc_source.confidence == Confidence.STRONGLY_INFERRED
    assert _blockers(template, "cfps", "feedback") == {
        ReadinessBlocker.NEEDS_NODE_ID_DISCOVERY,
        ReadinessBlocker.NEEDS_CONTROLS_APPROVAL_FOR_FIELD_SELECTION,
    }
    stabilization = next(item for item in feedback.candidates if item.address == "%IX52.4")
    assert stabilization.raw_symbol == "di_CFPS_StabilizationFb_Raw"
    assert "physical polarity remains unverified" in stabilization.note
    issue = next(
        item for item in template.global_issues if item.name == "cfps_stabilization_polarity"
    )
    assert issue.blocker == ReadinessBlocker.NEEDS_POLARITY_VERIFICATION


def test_cfps_power_is_missing_and_voltage_feedback_is_forbidden(template):
    power = _field(template, "cfps", "power")
    assert power.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
    forbidden = next(
        item for item in template.forbidden_substitutes if item.application_field == "cfps.power"
    )
    assert forbidden.physical_address == "%IW33"
    assert forbidden.plc_symbol.endswith("filamentData.Fb_FilamentPower_V")
    assert "not authoritative" in forbidden.reason
    assert "70 W/V" in forbidden.reason


@pytest.mark.parametrize(
    ("field_name", "path", "native_unit", "scale", "raw_address"),
    (
        ("voltage", "Application.PLC_PRG.daqData.IonPumpVoltage_kV", "kV", "1000", "%IW27"),
        ("current", "Application.PLC_PRG.daqData.IonPumpCurrent_mA", "mA", "0.001", "%IW28"),
    ),
)
def test_ipps_uses_processed_exports_and_narrow_module_blocker(
    template, field_name, path, native_unit, scale, raw_address
):
    field = _field(template, "ipps", field_name)
    blockers = _blockers(template, "ipps", field_name)
    assert field.exported_symbol_path.value == path
    assert field.plc_type.value == "REAL"
    assert field.native_unit.value == native_unit
    assert field.conversion.value == {"scale": scale, "offset": "0"}
    assert field.electrical_input_mode.value == "WAGO 750-471 0-10 V"
    assert field.electrical_input_mode.confidence == Confidence.CONFIRMED
    assert field.process_image_representation.value is None
    assert ReadinessBlocker.NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION in blockers
    assert ReadinessBlocker.NEEDS_RANGE_APPROVAL in blockers
    assert ReadinessBlocker.NEEDS_NODE_ID_DISCOVERY in blockers
    assert all(candidate.address != raw_address or "not the backend" in candidate.role for candidate in field.candidates)
    assert not any(field_name in str(item.node_id.value) for item in template.fields)


def test_ipps_hv_active_placeholder_is_machine_readable_and_forbidden(template):
    placeholder = next(
        item for item in template.forbidden_substitutes if item.application_field == "ipps.hv_active"
    )
    assert placeholder.plc_symbol == "FbHvActive := FALSE"
    assert "not mapped physical" in placeholder.reason
    assert ("ipps", "hv_active") not in EXPECTED_FIELDS


def test_arc_exports_are_preserved_without_inventing_an_aggregate(template):
    arc = _field(template, "arc_detector", "state")
    paths = {candidate.symbol for candidate in arc.candidates}
    blockers = _blockers(template, "arc_detector", "state")
    assert "Application.GVL_IntS.gIntS_Inp.ArcAlarm1_OK" in paths
    assert "Application.GVL_IntS.gIntS_Inp.ArcAlarm2_OK" in paths
    assert arc.exported_symbol_path.value is None
    assert arc.signal_selection.value is None
    assert arc.aggregation.value is None
    assert arc.severity.value is None
    assert ReadinessBlocker.NEEDS_SIGNAL_SELECTION in blockers
    assert ReadinessBlocker.NEEDS_AGGREGATION in blockers
    assert ReadinessBlocker.NEEDS_RECOVERY_SEMANTICS in blockers
    assert ReadinessBlocker.NEEDS_SEVERITY_APPROVAL in blockers


@pytest.mark.parametrize(
    ("equipment", "fault_path", "preset_address"),
    (
        ("ahvps", "Application.GVL_Alarms.gAlarms.ApsFault", "%QW27"),
        ("chvps", "Application.GVL_Alarms.gAlarms.CpsFault", "%QW24"),
    ),
)
def test_hvps_protection_is_confirmed_and_voltage_readback_missing(
    template, equipment, fault_path, preset_address
):
    protection = _field(template, equipment, "protection")
    voltage = _field(template, equipment, "voltage")
    assert protection.physical_source_status == PhysicalSourceStatus.PLC_SOURCE_CONFIRMED
    assert protection.exported_symbol_path.value == fault_path
    assert protection.plc_source.confidence == Confidence.CONFIRMED
    assert protection.interpretation.value == (
        "TRUE = InternalProtection OR Overcurrent OR Overvoltage OR Arc"
    )
    assert _blockers(template, equipment, "protection") == {
        ReadinessBlocker.NEEDS_NODE_ID_DISCOVERY
    }
    assert voltage.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
    forbidden = next(
        item
        for item in template.forbidden_substitutes
        if item.application_field == f"{equipment}.voltage"
    )
    assert forbidden.physical_address == preset_address
    if equipment == "chvps":
        assert "absence of a direct fbCPS export is not a blocker" in protection.notes[0]


def test_pulse_generator_fields_are_missing_and_preset_is_command_side(template):
    for field_name in ("state", "feedback", "pulse_length", "pulse_period"):
        assert (
            _field(template, "pulse_generator", field_name).physical_source_status
            == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
        )
    forbidden = next(
        item
        for item in template.forbidden_substitutes
        if item.application_field == "pulse_generator.length"
    )
    assert forbidden.physical_address == "%QW26"
    assert forbidden.plc_symbol.endswith("rSp_PulseDuration_V")
    assert "command-side" in forbidden.reason


def test_global_controls_issues_are_narrow_and_explicit(template):
    issues = {item.name: item for item in template.global_issues}
    module = issues["750_471_process_representation"]
    assert module.blocker == ReadinessBlocker.NEEDS_750_471_PROCESS_REPRESENTATION_VERIFICATION
    evidence = " ".join(module.evidence)
    for address in ("%IW27", "%IW28", "%IW29", "%IW30", "%IW31", "%IW32", "%IW33", "%IW34"):
        assert address in evidence
    assert "0-10 V electrical input mode" in evidence
    assert "exact numerical representation remains unresolved" in evidence
    assert issues["poor_vacuum_polarity"].blocker == ReadinessBlocker.NEEDS_POLARITY_VERIFICATION


def test_nodeid_plan_has_15_exports_no_nodeids_and_no_network_calls(template, monkeypatch, capsys):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("offline NodeId plan attempted a network call")

    monkeypatch.setattr(socket, "socket", network_forbidden)
    rendered = render_nodeid_discovery_plan(template)
    assert rendered.strip() == PLAN_PATH.read_text(encoding="utf-8").strip()
    assert "Preferred exported fields awaiting read-only discovery: **15**" in rendered
    assert rendered.count("\n| ") - 1 == 15
    assert "ns=" not in rendered
    assert "AccessLevel" in rendered
    assert "UserAccessLevel" in rendered
    assert main(["nodeid-plan", str(TEMPLATE_PATH)]) == 0
    assert "makes no network calls" in capsys.readouterr().out


def test_matrix_is_generated_from_template_with_required_columns(template):
    rendered = render_commissioning_matrix(template).strip()
    committed = MATRIX_PATH.read_text(encoding="utf-8").strip()
    assert committed == rendered
    for heading in (
        "Physical PLC source",
        "PLC variable",
        "Exported CODESYS symbol path",
        "Exported?",
        "Symbol access",
        "NodeId discovered?",
        "Remaining blockers",
    ):
        assert heading in rendered
    assert "Exported symbol confirmed: `15`" in rendered
    assert rendered.count("\n| ") >= len(template.fields)


def test_report_is_fail_closed_and_required_evidence_cannot_be_deleted(template, capsys):
    report = readiness_report(template)
    assert report.production_ready is False
    assert len(report.common_missing) == 10
    assert main(["validate", str(TEMPLATE_PATH)]) == 1
    assert "production_ready = false" in capsys.readouterr().out
    assert main(["report", str(TEMPLATE_PATH)]) == 0

    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["fields"][0]["requirements"] = []
    with pytest.raises(ValidationError, match="authoritative software contract"):
        ProductionCommissioningTemplate.model_validate(payload)
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["forbidden_substitutes"] = []
    with pytest.raises(ValidationError, match="forbidden readback substitutes"):
        ProductionCommissioningTemplate.model_validate(payload)


def test_invalid_template_load_is_reported_without_runtime_fallback(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"purpose":"production-template"}', encoding="utf-8")
    with pytest.raises(CommissioningTemplateError):
        load_commissioning_template(invalid)
