import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.opcua.commissioning import (
    EXPECTED_FIELDS,
    CommissioningTemplateError,
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


def _blockers(template, equipment: str, field: str):
    report = readiness_report(template)
    return set(
        next(
            item.blockers
            for item in report.fields
            if item.equipment == equipment and item.field == field
        )
    )


def test_template_has_complete_typed_equipment_contract_and_null_node_ids(template):
    actual = {(item.equipment, item.field): item.logical_signal for item in template.fields}

    assert template.purpose == "production-template"
    assert template.status == "incomplete"
    assert actual == EXPECTED_FIELDS
    assert len(template.fields) == 24
    assert all(item.node_id.value is None for item in template.fields)


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


def test_readiness_report_is_fail_closed_and_cli_validate_is_nonzero(template, capsys):
    report = readiness_report(template)

    assert report.production_ready is False
    assert set(report.common_missing) == {
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
    assert main(["validate", str(TEMPLATE_PATH)]) == 1
    assert "production_ready = false" in capsys.readouterr().out
    assert main(["report", str(TEMPLATE_PATH)]) == 0


def test_required_readiness_checks_cannot_be_deleted_to_fake_ready():
    payload = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    payload["fields"][0]["requirements"] = []

    with pytest.raises(ValidationError, match="authoritative software contract"):
        ProductionCommissioningTemplate.model_validate(payload)


def test_readiness_identifies_required_equipment_blockers(template):
    assert ReadinessBlocker.NEEDS_NODE_ID in _blockers(template, "cmps", "state")
    assert {
        ReadinessBlocker.BLOCKED_BY_PHYSICAL_SOURCE,
        ReadinessBlocker.NEEDS_NODE_ID,
        ReadinessBlocker.NEEDS_TYPE,
        ReadinessBlocker.NEEDS_CONVERSION,
        ReadinessBlocker.NEEDS_RANGE,
    }.issubset(_blockers(template, "cmps", "current"))
    assert ReadinessBlocker.NEEDS_CONVERSION in _blockers(template, "cfps", "power")
    assert ReadinessBlocker.NEEDS_RANGE in _blockers(template, "cfps", "power")
    assert {
        ReadinessBlocker.NEEDS_SIGNAL_SELECTION,
        ReadinessBlocker.NEEDS_POLARITY,
        ReadinessBlocker.NEEDS_INTERPRETATION,
    }.issubset(_blockers(template, "arc_detector", "state"))
    assert ReadinessBlocker.BLOCKED_BY_PHYSICAL_SOURCE in _blockers(
        template, "ahvps", "voltage"
    )
    assert ReadinessBlocker.BLOCKED_BY_PHYSICAL_SOURCE in _blockers(
        template, "chvps", "voltage"
    )
    for field in ("state", "feedback", "pulse_length", "pulse_period"):
        assert ReadinessBlocker.BLOCKED_BY_PHYSICAL_SOURCE in _blockers(
            template, "pulse_generator", field
        )


def test_recovered_candidates_and_unresolved_decisions_are_preserved(template):
    cmps_state = _field(template, "cmps", "state")
    assert cmps_state.candidates[0].address == "%IX49.3"
    assert cmps_state.candidates[0].symbol == "di_IntS_CMPS_On_Raw"
    assert cmps_state.interpretation.approved is False

    cfps_power = _field(template, "cfps", "power")
    assert cfps_power.candidates[0].address == "%IW33"
    assert "non-linear" in cfps_power.conversion.provenance
    assert cfps_power.conversion.value is None

    ipps_voltage = _field(template, "ipps", "voltage")
    ipps_current = _field(template, "ipps", "current")
    assert {item.address for item in ipps_voltage.candidates} == {"%IW27", None}
    assert {item.symbol for item in ipps_voltage.candidates} == {
        None,
        "Meas_Voltage_kV",
    }
    assert {item.address for item in ipps_current.candidates} == {"%IW28", None}
    assert {item.symbol for item in ipps_current.candidates} == {
        None,
        "Meas_Current_mA",
    }
    assert ipps_voltage.signal_selection.value is None
    assert ipps_current.signal_selection.value is None


def test_setpoint_outputs_are_explicitly_forbidden_as_actual_readbacks(template):
    expected = {
        ("ahvps", "voltage"): "%QW27",
        ("chvps", "voltage"): "%QW24",
        ("pulse_generator", "pulse_length"): "%QW26",
    }
    for key, address in expected.items():
        field = _field(template, *key)
        candidate = next(item for item in field.candidates if item.address == address)
        assert "FORBIDDEN" in candidate.note
        assert "setpoint" in candidate.role.lower() or "preset" in candidate.role.lower()
        assert field.node_id.value is None


def test_arc_candidates_keep_polarity_and_aggregation_unresolved(template):
    arc = _field(template, "arc_detector", "state")
    assert {item.address for item in arc.candidates} == {
        "%IX50.4",
        "%IX50.5",
        "%IX51.1",
        "%IX52.3",
    }
    assert arc.polarity.value is None
    assert arc.aggregation.value is None
    assert arc.latching.value is None
    assert arc.recovery.value is None
    assert arc.severity.value is None


def test_commissioning_matrix_is_generated_from_the_template(template):
    rendered = render_commissioning_matrix(template).strip()
    committed = MATRIX_PATH.read_text(encoding="utf-8").strip()

    assert committed == rendered
    assert "THIS IS NOT A PRODUCTION NODE MAP" in committed
    assert committed.count("\n| ") >= len(template.fields)


def test_invalid_template_load_is_reported_without_runtime_fallback(tmp_path: Path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"purpose":"production-template"}', encoding="utf-8")

    with pytest.raises(CommissioningTemplateError):
        load_commissioning_template(invalid)
