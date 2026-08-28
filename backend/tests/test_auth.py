from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core import auth
from app.core.config import get_settings
from app.core.sessions import session_manager
from app.models import UserRole


def test_authentication_uses_integer_receive_timeout_on_linux(monkeypatch):
    captured: dict[str, object] = {}

    def fake_server(host, **kwargs):
        captured["host"] = host
        captured["server_options"] = kwargs
        return object()

    class FakeConnection:
        def __init__(self, server, **kwargs):
            captured["server"] = server
            captured["connection_options"] = kwargs

        def unbind(self):
            captured["unbound"] = True

    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(
            ldap_server_host="ldap.test",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_timeout_seconds=5.25,
            ldap_domain="example.test",
        ),
    )
    monkeypatch.setattr(auth, "Server", fake_server)
    monkeypatch.setattr(auth, "Connection", FakeConnection)

    assert auth.authenticate_user("operator", "test-password") is True
    assert captured["server_options"]["connect_timeout"] == 5.25
    receive_timeout = captured["connection_options"]["receive_timeout"]
    assert receive_timeout == 6
    assert isinstance(receive_timeout, int)
    assert captured["unbound"] is True


def test_valid_login_creates_server_session(client: TestClient, authenticate):
    authenticate(True)

    response = client.post("/api/login", json={"username": "admin", "password": "valid"})

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=strict" in response.headers["set-cookie"].lower()
    assert client.get("/api/session").status_code == 200


def test_invalid_credentials_are_rejected(client: TestClient, authenticate):
    authenticate(False)
    response = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401


def test_missing_and_forged_sessions_are_rejected(client: TestClient):
    assert client.get("/api/status").status_code == 401

    client.cookies.set(get_settings().session_cookie_name, "forged-session")
    assert client.get("/api/status").status_code == 401


def test_expired_session_is_rejected(client: TestClient):
    session = session_manager.create("operator", UserRole.USER, ttl_seconds=-1)
    client.cookies.set(get_settings().session_cookie_name, session.token)
    assert client.get("/api/status").status_code == 401


def test_logout_invalidates_session(client: TestClient, authenticate):
    authenticate(True)
    assert client.post("/api/login", json={"username": "operator", "password": "valid"}).status_code == 200
    assert client.post("/api/logout").status_code == 204
    assert client.get("/api/session").status_code == 401
