import json
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
)
from app.opcua.node_map import NodeMapError, NodeMapping, load_node_map


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
TEMPLATE_PATH = BACKEND_ROOT / "config" / "opcua_nodes.production.template.json"
MATRIX_PATH = REPOSITORY_ROOT / "docs" / "opcua_production_commissioning.md"


@pytest.fixture(scope="module")
def template():
    return load_commissioning_template(TEMPLATE_PATH)


def _field(template, equipment: str, field: str):
    return next(
        item
        for item in template.fields
        if item.equipment == equipment and item.field == field
    )


def _readiness(template, equipment: str, field: str):
    return next(
        item
        for item in readiness_report(template).fields
        if item.equipment == equipment and item.field == field
    )


def _blockers(template, equipment: str, field: str):
    return set(_readiness(template, equipment, field).blockers)


def test_template_has_complete_contract_null_node_ids_and_derived_counts(template):
    actual = {(item.equipment, item.field): item.logical_signal for item in template.fields}
    report = readiness_report(template)

    assert template.schema_version == 2
    assert template.purpose == "production-template"
    assert template.status == "incomplete"
    assert actual == EXPECTED_FIELDS
    assert len(template.fields) == 24
    assert all(item.node_id.value is None for item in template.fields)
    assert report.counts.plc_source_confirmed == 12
    assert report.counts.partially_resolved == 4
    assert report.counts.missing_physical_source == 8
    assert report.counts.needs_opcua_discovery == 16


def test_commissioning_template_is_not_a_runtime_node_map(template):
    with pytest.raises(NodeMapError):
        load_node_map(TEMPLATE_PATH)

    with pytest.raises(ValidationError):
        NodeMapping(
            signal="cmps.current",
            node_id=None,
            expected_type="float",
            unit="A",
        )


def test_changing_only_purpose_cannot_bypass_either_schema(tmp_path: Path):
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["purpose"] = "production"

    with pytest.raises(ValidationError):
        ProductionCommissioningTemplate.model_validate(payload)

    changed = tmp_path / "purpose-only.json"
    changed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(NodeMapError):
        load_node_map(changed)


def test_testonly_node_ids_are_rejected_by_template_and_runtime(tmp_path: Path):
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["fields"][0]["node_id"] = {
        "value": "ns=2;s=TestOnly.Gyrotron.CMPS.State",
        "confidence": "confirmed",
        "approved": True,
        "provenance": "Test fixture",
    }
    with pytest.raises(ValidationError, match="forbidden"):
        ProductionCommissioningTemplate.model_validate(payload)

    payload["purpose"] = "production"
    path = tmp_path / "testonly-production.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(NodeMapError):
        load_node_map(path)


def test_report_remains_fail_closed_and_cli_validate_is_nonzero(template, capsys):
    report = readiness_report(template)

    assert report.production_ready is False
    assert len(report.common_missing) == 10
    assert set(report.global_blockers) == {
        ReadinessBlocker.NEEDS_750_471_CONFIGURATION,
        ReadinessBlocker.NEEDS_POLARITY_VERIFICATION,
    }
    assert main(["validate", str(TEMPLATE_PATH)]) == 1
    assert "production_ready = false" in capsys.readouterr().out
    assert main(["report", str(TEMPLATE_PATH)]) == 0


def test_missing_source_classification_is_itself_a_production_readiness_gate(template):
    report = readiness_report(template)
    missing = [
        field
        for field in report.fields
        if field.source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
    ]

    assert len(missing) == 8
    assert all(not field.blockers for field in missing)
    assert report.production_ready is False


def test_required_readiness_and_global_checks_cannot_be_deleted():
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["fields"][0]["requirements"] = []
    with pytest.raises(ValidationError, match="authoritative software contract"):
        ProductionCommissioningTemplate.model_validate(payload)

    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["global_issues"] = []
    with pytest.raises(ValidationError, match="global commissioning issues"):
        ProductionCommissioningTemplate.model_validate(payload)


def test_controller_and_hvps_identities_are_confirmed_without_versions(template):
    assert template.controller.vendor.value == "WAGO"
    assert template.controller.model.value == "PFC200 750-8210"
    assert template.controller.runtime.value == "CODESYS-based"
    assert template.controller.runtime_version.value is None
    assert template.controller.opcua_server_version.value is None
    assert {
        (item.application_equipment, item.plc_equipment, item.meaning)
        for item in template.equipment_identities
    } == {
        ("AHVPS", "APS", "Anode Power Supply"),
        ("CHVPS", "CPS", "Cathode Power Supply"),
    }
    assert all(item.confidence == Confidence.CONFIRMED for item in template.equipment_identities)


def test_cmps_sources_and_missing_actual_current_are_classified(template):
    state = _field(template, "cmps", "state")
    current = _field(template, "cmps", "current")
    authorization = _field(template, "cmps", "interlock")

    assert state.physical_source_status == PhysicalSourceStatus.PLC_SOURCE_CONFIRMED
    assert state.plc_source.value == "gIntS_Inp.CMPS_On"
    assert state.candidates[0].raw_symbol == "di_IntS_CMPS_On_Raw"
    assert _blockers(template, "cmps", "state") == {
        ReadinessBlocker.NEEDS_OPCUA_DISCOVERY
    }
    assert current.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
    assert current.plc_source.value is None
    assert not _blockers(template, "cmps", "current")
    assert authorization.plc_source.value == "gIntS_Outp.Auth_CMPS"
    assert "not independent equipment feedback" in authorization.candidates[0].role


def test_cfps_evidence_keeps_power_missing_and_feedback_partial(template):
    state = _field(template, "cfps", "state")
    power = _field(template, "cfps", "power")
    feedback = _field(template, "cfps", "feedback")
    authorization = _field(template, "cfps", "interlock")

    assert state.physical_source_status == PhysicalSourceStatus.PLC_SOURCE_CONFIRMED
    assert power.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
    iw33 = next(item for item in power.candidates if item.address == "%IW33")
    assert "FORBIDDEN" in iw33.note
    assert "70 W/V" in " ".join(power.notes)
    assert feedback.physical_source_status == PhysicalSourceStatus.NEEDS_CONTROLS_VERIFICATION
    assert feedback.plc_source.value == "filamentData.Sts_Run"
    assert feedback.plc_source.confidence == Confidence.STRONGLY_INFERRED
    stabilization = next(item for item in feedback.candidates if item.address == "%IX52.4")
    assert "low means stabilization active" in stabilization.note
    assert "unverified" in stabilization.note
    assert authorization.plc_source.value == "gIntS_Outp.Auth_CFPS"
    assert "WaterFlow AND IPPS_On AND PoorVacuum_OK" in authorization.interpretation.provenance
    assert "CMPS" not in authorization.interpretation.provenance


@pytest.mark.parametrize(
    ("field_name", "raw_address", "raw_symbol", "processed_symbol"),
    (
        ("voltage", "%IW27", "ai_IonPumpVoltage_Raw", "ippsData.Meas_Voltage_kV"),
        ("current", "%IW28", "ai_IonPumpCurrent_Raw", "ippsData.Meas_Current_mA"),
    ),
)
def test_ipps_measurements_confirm_sources_but_keep_export_and_module_blockers(
    template, field_name, raw_address, raw_symbol, processed_symbol
):
    field = _field(template, "ipps", field_name)
    blockers = _blockers(template, "ipps", field_name)

    assert field.physical_source_status == PhysicalSourceStatus.PLC_SOURCE_CONFIRMED
    assert {(item.address, item.symbol) for item in field.candidates} == {
        (raw_address, raw_symbol),
        (None, processed_symbol),
    }
    assert ReadinessBlocker.NEEDS_750_471_CONFIGURATION in blockers
    assert ReadinessBlocker.NEEDS_EXPORTED_SYMBOL_SELECTION in blockers
    assert ReadinessBlocker.NEEDS_RANGE_APPROVAL in blockers
    assert ReadinessBlocker.NEEDS_OPCUA_DISCOVERY in blockers


def test_ipps_state_authorization_and_hv_active_warning_are_preserved(template):
    state = _field(template, "ipps", "state")
    authorization = _field(template, "ipps", "interlock")

    assert state.plc_source.value == "ippsData.Sts_On / gIntS_Inp.IPPS_On"
    assert "supplies FALSE" in " ".join(state.notes)
    assert "not production feedback" in " ".join(state.notes)
    assert authorization.plc_source.value == "gIntS_Outp.Auth_IPPS"
    assert "DoorsClosed" in authorization.interpretation.provenance


def test_arc_polarities_are_confirmed_but_aggregate_remains_unresolved(template):
    arc = _field(template, "arc_detector", "state")
    roles = {item.address: item.role for item in arc.candidates}
    blockers = _blockers(template, "arc_detector", "state")

    assert "raw TRUE = healthy/OK" in roles["%IX50.4"]
    assert "raw FALSE = healthy/OK" in roles["%IX50.5"]
    assert "explicitly inverts" in next(
        item.note for item in arc.candidates if item.address == "%IX50.5"
    )
    assert arc.physical_source_status == PhysicalSourceStatus.NEEDS_CONTROLS_VERIFICATION
    assert arc.signal_selection.value is None
    assert arc.aggregation.value is None
    assert ReadinessBlocker.NEEDS_SIGNAL_SELECTION in blockers
    assert ReadinessBlocker.NEEDS_AGGREGATION in blockers
    assert ReadinessBlocker.NEEDS_SEVERITY_APPROVAL in blockers


@pytest.mark.parametrize(
    ("equipment", "plc_prefix", "state_symbol", "state_address", "setpoint", "fault"),
    (
        ("ahvps", "APS", "gIntS_Inp.APS_On", "%IX50.1", "%QW27", "PLC_PRG.fbAPS.StatusFault"),
        ("chvps", "CPS", "gIntS_Inp.CPS_On", "%IX50.0", "%QW24", "PLC_PRG.fbCPS.StatusFault"),
    ),
)
def test_hvps_state_is_confirmed_voltage_missing_and_protection_partial(
    template, equipment, plc_prefix, state_symbol, state_address, setpoint, fault
):
    state = _field(template, equipment, "state")
    voltage = _field(template, equipment, "voltage")
    protection = _field(template, equipment, "protection")
    authorization = _field(template, equipment, "interlock")

    assert state.physical_source_status == PhysicalSourceStatus.PLC_SOURCE_CONFIRMED
    assert state.plc_source.value == state_symbol
    assert state.candidates[0].address == state_address
    assert voltage.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
    output = next(item for item in voltage.candidates if item.address == setpoint)
    assert "SETPOINT" in output.role
    assert "FORBIDDEN" in output.note
    assert protection.physical_source_status == PhysicalSourceStatus.NEEDS_CONTROLS_VERIFICATION
    assert protection.plc_source.value == fault
    assert protection.plc_source.confidence == Confidence.STRONGLY_INFERRED
    assert ReadinessBlocker.NEEDS_CURRENT_FB_VERIFICATION in _blockers(
        template, equipment, "protection"
    )
    assert authorization.plc_source.value == f"gIntS_Outp.Auth_{plc_prefix}"


def test_all_pulse_generator_fields_are_missing_and_preset_is_forbidden(template):
    for field_name in ("state", "feedback", "pulse_length", "pulse_period"):
        field = _field(template, "pulse_generator", field_name)
        assert field.physical_source_status == PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
        assert _readiness(template, "pulse_generator", field_name).source_status == (
            PhysicalSourceStatus.MISSING_PHYSICAL_SOURCE
        )

    pulse_length = _field(template, "pulse_generator", "pulse_length")
    preset = next(item for item in pulse_length.candidates if item.address == "%QW26")
    assert "PRESET" in preset.role
    assert "FORBIDDEN" in preset.note


def test_global_750_471_and_poor_vacuum_issues_are_explicit(template):
    issues = {item.name: item for item in template.global_issues}
    module = issues["750_471_parameterization"]
    vacuum = issues["poor_vacuum_polarity"]

    assert module.blocker == ReadinessBlocker.NEEDS_750_471_CONFIGURATION
    evidence = " ".join(module.evidence)
    for address in ("%IW27", "%IW28", "%IW29", "%IW30", "%IW31", "%IW32", "%IW33", "%IW34"):
        assert address in evidence
    assert "not production-approved" in evidence
    assert vacuum.blocker == ReadinessBlocker.NEEDS_POLARITY_VERIFICATION
    assert "PoorVacuum_OK := di_IntS_PoorVacuum_Raw" in " ".join(vacuum.evidence)


def test_matrix_is_generated_from_template_with_refined_columns(template):
    rendered = render_commissioning_matrix(template).strip()
    committed = MATRIX_PATH.read_text(encoding="utf-8").strip()

    assert committed == rendered
    assert "THIS IS NOT A PRODUCTION NODE MAP" in committed
    assert "PLC logical candidate" in committed
    assert "Raw PLC symbol" in committed
    assert "OPC UA discovery status" in committed
    assert "PLC source confirmed: `12`" in committed
    assert committed.count("\n| ") >= len(template.fields)


def test_invalid_template_load_is_reported_without_runtime_fallback(tmp_path: Path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"purpose":"production-template"}', encoding="utf-8")

    with pytest.raises(CommissioningTemplateError):
        load_commissioning_template(invalid)
