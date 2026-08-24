import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import AppSettings
from app.core import safety
from app.core.sessions import session_manager
from app.main import create_app
from app.models import (
    AppMode,
    ConnectionState,
    DataSource,
    DataState,
    SignalQuality,
    SignalValue,
    TelemetryPoint,
    UserRole,
)
from app.opcua.client import ReadOnlyOPCUAClient
from app.opcua.monitor import MonitorView
from app.opcua.node_map import LogicalSignal
from tests.opcua_simulator import TEST_UNITS, make_opcua_settings


def _node_map_file(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "purpose": "production",
                "signals": [
                    {
                        "signal": signal.value,
                        "node_id": f"ns=2;s=Approved.{signal.value}",
                        "expected_type": "float",
                        "unit": TEST_UNITS[signal],
                    }
                    for signal in LogicalSignal
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _app_settings(mode: AppMode, event_db_path: Path, opcua=None) -> AppSettings:
    return AppSettings(
        app_mode=mode,
        cors_origins=("http://localhost:5173",),
        ldap_server_host="ldap.invalid.test",
        ldap_domain="invalid.test",
        ldap_port=636,
        ldap_use_ssl=True,
        ldap_timeout_seconds=1,
        session_cookie_name="gyro_session",
        session_ttl_seconds=3600,
        session_cookie_secure=False,
        event_db_path=event_db_path,
        opcua=opcua,
    )


def _snapshot() -> TelemetryPoint:
    now = datetime.now(timezone.utc)
    samples = {
        signal.value: SignalValue(
            value=float(index),
            unit=TEST_UNITS[signal],
            quality=SignalQuality.GOOD,
            source_timestamp=now,
        )
        for index, signal in enumerate(LogicalSignal, start=1)
    }
    return TelemetryPoint(
        timestamp=now,
        source=DataSource.OPCUA,
        sequence=7,
        **samples,
    )


class FakeMonitor:
    def __init__(self, view: MonitorView) -> None:
        self.current_view = view
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    def view(self) -> MonitorView:
        return self.current_view


def _authenticated_client(app, user_manager):
    user_manager.add_user("readonly-operator", UserRole.USER)
    test_client = TestClient(app)
    session = session_manager.create("readonly-operator", UserRole.USER)
    test_client.cookies.set("gyro_session", session.token)
    return test_client


def test_simulation_lifecycle_never_constructs_an_opcua_client(tmp_path: Path):
    def forbidden_factory(_settings, _node_map):
        raise AssertionError("simulation mode attempted to construct an OPC UA monitor")

    app = create_app(
        _app_settings(AppMode.SIMULATION, tmp_path / "events.sqlite3"),
        monitor_factory=forbidden_factory,
    )
    with TestClient(app):
        assert app.state.opcua_monitor is None


def test_readonly_lifecycle_starts_cache_and_api_uses_snapshot(tmp_path: Path, user_manager):
    node_map_path = _node_map_file(tmp_path / "nodes.json")
    opcua = make_opcua_settings("opc.tcp://127.0.0.1:4840/test/", node_map_path)
    now = datetime.now(timezone.utc)
    monitor = FakeMonitor(
        MonitorView(
            connection_state=ConnectionState.CONNECTED,
            data_state=DataState.LIVE,
            last_connection_attempt=now,
            last_successful_read=now,
            snapshot=_snapshot(),
            error=None,
        )
    )
    app = create_app(
        _app_settings(AppMode.OPCUA_READONLY, tmp_path / "events.sqlite3", opcua),
        monitor_factory=lambda _settings, _node_map: monitor,
    )

    with _authenticated_client(app, user_manager) as client:
        assert monitor.started
        telemetry = client.get("/api/telemetry")
        assert telemetry.status_code == 200
        assert telemetry.json()["source"] == "opcua"
        assert telemetry.json()["ionV"]["quality"] == "good"
        status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["mode"] == "opcua_readonly"
        assert status.json()["overall_state"] == "unknown"
        assert status.json()["cps"]["state"] == "unknown"
    assert monitor.stopped


def test_readonly_api_returns_explicit_unavailable_without_snapshot(tmp_path: Path, user_manager):
    node_map_path = _node_map_file(tmp_path / "nodes.json")
    opcua = make_opcua_settings("opc.tcp://127.0.0.1:4840/test/", node_map_path)
    monitor = FakeMonitor(
        MonitorView(
            connection_state=ConnectionState.ERROR,
            data_state=DataState.UNAVAILABLE,
            last_connection_attempt=datetime.now(timezone.utc),
            last_successful_read=None,
            snapshot=None,
            error="OPC UA connection failed",
        )
    )
    app = create_app(
        _app_settings(AppMode.OPCUA_READONLY, tmp_path / "events.sqlite3", opcua),
        monitor_factory=lambda _settings, _node_map: monitor,
    )
    with _authenticated_client(app, user_manager) as client:
        response = client.get("/api/telemetry")
        assert response.status_code == 503
        assert response.json()["detail"] == "OPC UA telemetry is unavailable"


def test_readonly_boundary_exposes_no_write_capability(client, authenticate):
    forbidden = {
        "write_node",
        "write_value",
        "set_value",
        "set_data_value",
        "command",
        "reset",
        "acknowledge",
        "setpoint",
    }
    assert forbidden.isdisjoint(dir(ReadOnlyOPCUAClient))
    assert not hasattr(safety, "emergency_stop")
    assert not hasattr(safety, "check_safety_interlocks")

    hardware_routes = {
        "/api/write",
        "/api/reset",
        "/api/emergency-stop",
        "/api/interlocks/reset",
        "/api/cps",
        "/api/aps",
        "/api/alarms/acknowledge",
        "/api/alarm/ack",
    }
    assert hardware_routes.isdisjoint({route.path for route in client.app.routes})

    authenticate(True)
    response = client.post("/api/login", json={"username": "operator", "password": "valid"})
    assert response.status_code == 200
    assert client.post("/api/setpoint").status_code == 503


def test_production_opcua_code_contains_no_write_invocation():
    app_root = Path(__file__).resolve().parents[1] / "app"
    source = "\n".join(path.read_text(encoding="utf-8") for path in app_root.rglob("*.py"))
    forbidden_calls = (
        ".write_node(",
        ".write_value(",
        ".set_value(",
        ".set_data_value(",
    )
    assert all(call not in source for call in forbidden_calls)
