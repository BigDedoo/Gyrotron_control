import json
import socket
from pathlib import Path

import pytest

from app.opcua.node_map import NodeMapError, load_node_map
from app.opcua.reconciliation import (
    DiscoveredNodeError,
    DiscoveredNodeSet,
    ReconciliationStatus,
    generate_draft_map,
    load_discovered_nodes,
    reconcile_files,
    reconcile_discovered_nodes,
)
from app.opcua.commissioning import load_commissioning_template


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "config" / "opcua_nodes.production.template.json"
DISCOVERED = Path(__file__).parent / "commissioning" / "fixtures" / "discovered-full-good.json"


def _payload() -> dict:
    return json.loads(DISCOVERED.read_text(encoding="utf-8"))


def test_canonical_input_is_strict_and_full_fixture_reconciles_exactly(tmp_path: Path):
    result = reconcile_files(TEMPLATE, DISCOVERED)
    assert result.expected_count == 15
    assert result.ready_count == 15
    assert {field.status for field in result.fields} == {
        ReconciliationStatus.READY_FOR_DRAFT_MAP
    }

    invalid = _payload()
    invalid["unexpected"] = True
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")
    with pytest.raises(DiscoveredNodeError):
        load_discovered_nodes(path)


def test_missing_ambiguous_datatype_access_unit_and_no_fuzzy_match():
    template = load_commissioning_template(TEMPLATE)
    payload = _payload()
    payload["nodes"] = payload["nodes"][1:]
    payload["nodes"][0]["symbol_path"] = "Application.GVL_IntS.gIntS_Inp.CMPS_On_SIMILAR"
    missing = reconcile_discovered_nodes(template, DiscoveredNodeSet.model_validate(payload))
    assert next(field for field in missing.fields if field.logical_signal == "cmps.state").status == ReconciliationStatus.MISSING

    payload = _payload()
    duplicate = dict(payload["nodes"][0])
    duplicate["node_id"] = "ns=2;s=TestOnly.Discovered.CMPS_On.Second"
    payload["nodes"].append(duplicate)
    ambiguous = reconcile_discovered_nodes(template, DiscoveredNodeSet.model_validate(payload))
    assert next(field for field in ambiguous.fields if field.logical_signal == "cmps.state").status == ReconciliationStatus.AMBIGUOUS

    cases = (
        ("data_type", "STRING", ReconciliationStatus.DATATYPE_MISMATCH),
        ("user_access_level", "CurrentRead CurrentWrite", ReconciliationStatus.ACCESS_WARNING),
        ("engineering_unit", "V", ReconciliationStatus.UNIT_WARNING),
    )
    for key, value, expected in cases:
        payload = _payload()
        node = next(item for item in payload["nodes"] if item["symbol_path"].endswith("IonPumpVoltage_kV"))
        node[key] = value
        result = reconcile_discovered_nodes(template, DiscoveredNodeSet.model_validate(payload))
        assert next(field for field in result.fields if field.logical_signal == "ipps.voltage").status == expected


def test_draft_contains_only_ready_preferred_sources_and_is_not_runnable(tmp_path: Path):
    result = reconcile_files(TEMPLATE, DISCOVERED)
    draft = generate_draft_map(result)
    logical = {item["signal"] for item in (*draft["signals"], *draft["state_signals"])}
    assert len(logical) == 15
    assert {"ipps.voltage", "ipps.current"}.issubset(logical)
    assert not logical.intersection({
        "cmps.current", "cfps.power", "ahvps.voltage", "chvps.voltage",
        "pulse_generator.state", "pulse_generator.feedback",
        "pulse_generator.length", "pulse_generator.period", "alarm.arc_detector",
    })
    assert draft["purpose"] == "draft-production"
    assert draft["approved"] is False

    path = tmp_path / "draft.json"
    path.write_text(json.dumps(draft), encoding="utf-8")
    with pytest.raises(NodeMapError):
        load_node_map(path)
    draft["purpose"] = "production"
    path.write_text(json.dumps(draft), encoding="utf-8")
    with pytest.raises(NodeMapError):
        load_node_map(path)


def test_reconciliation_opens_no_socket(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network attempted")))
    assert reconcile_files(TEMPLATE, DISCOVERED).ready_count == 15
