import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models import InterpretedState
from app.opcua.node_map import (
    LogicalSignal,
    LogicalStateSignal,
    NodeMap,
    NodeMapError,
    StateNodeMapping,
    load_node_map,
)
from tests.opcua_simulator import TEST_UNITS


def _telemetry_mappings() -> list[dict]:
    return [
        {
            "signal": signal.value,
            "node_id": f"ns=2;s=Approved.{signal.value}",
            "expected_type": "float",
            "unit": TEST_UNITS[signal],
        }
        for signal in LogicalSignal
    ]


def _state_mapping(signal: str = "interlock.gs_doors") -> dict:
    return {
        "signal": signal,
        "node_id": f"ns=2;s=Approved.{signal}",
        "expected_type": "boolean",
        "interpretation": {"true": "ok", "false": "fault"},
    }


def test_boolean_state_mapping_requires_explicit_polarity():
    mapping = StateNodeMapping.model_validate(_state_mapping())
    assert mapping.interpret(True) == InterpretedState.OK
    assert mapping.interpret(False) == InterpretedState.FAULT

    inverse = _state_mapping("interlock.poor_vacuum")
    inverse["interpretation"] = {"true": "fault", "false": "ok"}
    mapping = StateNodeMapping.model_validate(inverse)
    assert mapping.interpret(True) == InterpretedState.FAULT
    assert mapping.interpret(False) == InterpretedState.OK

    for interpretation in ({}, {"true": "ok"}, {"false": "fault"}):
        invalid = _state_mapping()
        invalid["interpretation"] = interpretation
        with pytest.raises(ValidationError, match="explicit true and false"):
            StateNodeMapping.model_validate(invalid)


def test_integer_state_mapping_is_explicit_and_rejects_invalid_enum_keys():
    mapping = StateNodeMapping(
        signal=LogicalStateSignal.CPS_STATE,
        node_id="ns=2;s=Approved.CPS.State",
        expected_type="integer",
        interpretation={"0": "off", "1": "on", "2": "fault"},
    )
    assert mapping.interpret(0) == InterpretedState.OFF
    assert mapping.interpret(2) == InterpretedState.FAULT
    assert mapping.interpret(99) == InterpretedState.UNKNOWN

    invalid = mapping.model_dump(mode="json")
    invalid["interpretation"] = {"01": "on"}
    with pytest.raises(ValidationError, match="canonical"):
        StateNodeMapping.model_validate(invalid)


def test_duplicate_state_names_and_node_ids_are_rejected():
    first = _state_mapping()
    duplicate_name = {**first, "node_id": "ns=2;s=Approved.Other"}
    with pytest.raises(ValidationError, match="logical state signal"):
        NodeMap(
            schema_version=1,
            purpose="production",
            signals=_telemetry_mappings(),
            state_signals=[first, duplicate_name],
        )

    duplicate_node = _state_mapping("interlock.waterflow")
    duplicate_node["node_id"] = "ns=2;s=Approved.ionV"
    with pytest.raises(ValidationError, match="node IDs"):
        NodeMap(
            schema_version=1,
            purpose="production",
            signals=_telemetry_mappings(),
            state_signals=[duplicate_node],
        )


def test_partial_production_state_map_is_explicitly_allowed_but_template_is_not(tmp_path: Path):
    path = tmp_path / "partial.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "purpose": "production",
                "signals": _telemetry_mappings(),
                "state_signals": [_state_mapping()],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_node_map(path)
    assert set(loaded.states_by_signal()) == {LogicalStateSignal.GS_DOORS}

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["purpose"] = "template"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(NodeMapError, match="not allowed"):
        load_node_map(path)


def test_state_map_rejects_test_nodes_invalid_semantics_and_invalid_severity():
    test_node = _state_mapping()
    test_node["node_id"] = "ns=2;s=TestOnly.Gyrotron.Doors"
    with pytest.raises(ValidationError, match="test-only"):
        NodeMap(
            schema_version=1,
            purpose="production",
            signals=_telemetry_mappings(),
            state_signals=[test_node],
        )

    invalid_semantics = _state_mapping()
    invalid_semantics["interpretation"] = {"true": "on", "false": "off"}
    with pytest.raises(ValidationError, match="must use only"):
        StateNodeMapping.model_validate(invalid_semantics)

    invalid_severity = {
        "signal": "alarm.arc_detector",
        "node_id": "ns=2;s=Approved.Alarm.Arc",
        "expected_type": "boolean",
        "interpretation": {"true": "active", "false": "inactive"},
        "alarm_severity": "catastrophic",
    }
    with pytest.raises(ValidationError):
        StateNodeMapping.model_validate(invalid_severity)
