import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import AppSettings, OPCUASettings
from app.opcua.node_map import LogicalSignal, NodeMapError, load_node_map
from tests.opcua_simulator import TEST_UNITS


def _write_map(path: Path, *, purpose: str = "production", omit: LogicalSignal | None = None) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "purpose": purpose,
                "signals": [
                    {
                        "signal": signal.value,
                        "node_id": f"ns=2;s=Approved.{signal.value}",
                        "expected_type": "float",
                        "unit": TEST_UNITS[signal],
                    }
                    for signal in LogicalSignal
                    if signal != omit
                ],
            }
        ),
        encoding="utf-8",
    )


def test_production_node_map_requires_every_unique_logical_signal(tmp_path: Path):
    valid = tmp_path / "valid.json"
    _write_map(valid)
    node_map = load_node_map(valid)
    assert set(node_map.by_signal()) == set(LogicalSignal)

    missing = tmp_path / "missing.json"
    _write_map(missing, omit=LogicalSignal.T_COLD)
    with pytest.raises(NodeMapError):
        load_node_map(missing)


def test_template_and_placeholder_maps_cannot_be_used_as_production(tmp_path: Path):
    template = tmp_path / "template.json"
    _write_map(template, purpose="template")
    with pytest.raises(NodeMapError, match="not allowed"):
        load_node_map(template)

    payload = json.loads(template.read_text(encoding="utf-8"))
    payload["purpose"] = "production"
    payload["signals"][0]["node_id"] = "CONFIGURE_ME"
    template.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(NodeMapError):
        load_node_map(template)

    copied_template = tmp_path / "copied-template.json"
    _write_map(copied_template)
    copied_payload = json.loads(copied_template.read_text(encoding="utf-8"))
    copied_payload["signals"][0]["node_id"] = "ns=2;s=TestOnly.Gyrotron.ionV"
    copied_template.write_text(json.dumps(copied_payload), encoding="utf-8")
    with pytest.raises(NodeMapError):
        load_node_map(copied_template)


def test_secure_configuration_cannot_silently_downgrade(tmp_path: Path):
    node_map = tmp_path / "nodes.json"
    _write_map(node_map)
    with pytest.raises(ValidationError, match="client certificate and private key"):
        OPCUASettings(
            endpoint_url="opc.tcp://127.0.0.1:4840/",
            connect_timeout_seconds=1,
            read_timeout_seconds=1,
            monitor_interval_seconds=1,
            reconnect_initial_seconds=1,
            reconnect_max_seconds=2,
            stale_after_seconds=3,
            node_map_path=node_map,
            security_policy="Basic256Sha256",
            security_mode="SignAndEncrypt",
        )


def test_readonly_mode_requires_explicit_endpoint_and_node_map(monkeypatch):
    monkeypatch.setenv("APP_MODE", "opcua_readonly")
    monkeypatch.delenv("OPCUA_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("OPCUA_NODE_MAP_PATH", raising=False)
    with pytest.raises(ValueError, match="OPCUA_ENDPOINT_URL is required"):
        AppSettings.from_environment()


def test_simulation_ignores_opcua_configuration_and_remains_isolated(monkeypatch):
    monkeypatch.setenv("APP_MODE", "simulation")
    monkeypatch.setenv("OPCUA_ENDPOINT_URL", "opc.tcp://real-plc.invalid:4840/")
    monkeypatch.setenv("OPCUA_NODE_MAP_PATH", "missing.json")
    settings = AppSettings.from_environment()
    assert settings.opcua is None
