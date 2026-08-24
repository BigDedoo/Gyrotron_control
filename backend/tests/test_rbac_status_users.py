from fastapi.testclient import TestClient

from app.core.users import UserManager, UserStorageError


def login(client: TestClient, authenticate, username: str) -> None:
    authenticate(True)
    response = client.post("/api/login", json={"username": username, "password": "valid"})
    assert response.status_code == 200


def test_normal_user_cannot_access_admin_operations(client: TestClient, authenticate):
    login(client, authenticate, "operator")
    assert client.get("/api/users").status_code == 403
    assert client.post(
        "/api/users/add", json={"username": "new-user", "role": "user"}
    ).status_code == 403


def test_admin_can_manage_users(client: TestClient, authenticate):
    login(client, authenticate, "admin")
    response = client.post("/api/users/add", json={"username": "new-user", "role": "user"})
    assert response.status_code == 201
    assert any(user["username"] == "new-user" for user in response.json()["users"])


def test_invalid_role_is_rejected(client: TestClient, authenticate):
    login(client, authenticate, "admin")
    response = client.post("/api/users/add", json={"username": "new-user", "role": "superuser"})
    assert response.status_code == 422


def test_unauthorized_user_mutation_is_rejected(client: TestClient):
    response = client.post("/api/users/remove", json={"username": "operator"})
    assert response.status_code == 401


def test_user_store_errors_propagate(
    client: TestClient,
    authenticate,
    user_manager: UserManager,
    monkeypatch,
):
    login(client, authenticate, "admin")

    def fail_save(_username, _role):
        raise UserStorageError("disk unavailable")

    monkeypatch.setattr(user_manager, "add_user", fail_save)
    response = client.post("/api/users/add", json={"username": "new-user", "role": "user"})
    assert response.status_code == 500
    assert response.json()["detail"] == "User store operation failed"


def test_status_is_explicit_simulation_with_unknown_hardware(
    client: TestClient,
    authenticate,
):
    login(client, authenticate, "operator")
    response = client.get("/api/status")
    assert response.status_code == 200
    status = response.json()
    assert status["mode"] == "simulation"
    assert status["source"] == "simulation"
    assert status["connection_state"] == "simulated"
    assert status["overall_state"] == "simulation"
    assert status["cps"]["state"] == "unknown"
    assert status["aps"]["state"] == "unknown"
    assert all(interlock["state"] == "unknown" for interlock in status["interlocks"])
    assert status["coverage"]["mapped"] == 0
    assert status["coverage"]["complete"] is False


def test_request_or_frontend_state_cannot_override_authoritative_status(
    client: TestClient,
    authenticate,
):
    login(client, authenticate, "operator")
    response = client.get("/api/status?cps=on&aps=on&ready=ok")
    assert response.status_code == 200
    assert response.json()["cps"]["state"] == "unknown"
    assert response.json()["aps"]["state"] == "unknown"


def test_telemetry_is_typed_and_explicitly_simulated(client: TestClient, authenticate):
    login(client, authenticate, "operator")
    response = client.get("/api/telemetry")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "simulation"
    assert payload["timestamp"]
    assert payload["ionV"]["value"] is not None
    assert payload["ionV"]["unit"] == "V"
    assert payload["ionV"]["quality"] == "good"
    assert payload["ionV"]["source_timestamp"]


def test_setpoint_endpoint_refuses_fake_commands(client: TestClient, authenticate):
    login(client, authenticate, "operator")
    response = client.post("/api/setpoint")
    assert response.status_code == 503
