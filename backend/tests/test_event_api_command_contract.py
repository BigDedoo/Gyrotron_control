import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.commands.capabilities import CommandBlocker, phase4_capabilities
from app.commands.contracts import CommandContractTemplate
from app.events.models import EventCategory


def _login(client: TestClient, authenticate, username: str = "operator") -> None:
    authenticate(True)
    response = client.post("/api/login", json={"username": username, "password": "valid"})
    assert response.status_code == 200


def test_event_api_requires_authentication_and_has_no_client_mutation_routes(client):
    assert client.get("/api/events").status_code == 401
    assert client.post("/api/events", json={}).status_code == 405
    assert client.put("/api/events", json={}).status_code == 405
    assert client.delete("/api/events").status_code == 405
    assert "application.started" in {
        event.event_type for event in client.app.state.event_store.query(limit=10)
    }


def test_event_api_reports_unavailable_store(client, authenticate):
    _login(client, authenticate)
    client.app.state.event_store.available = False
    assert client.get("/api/events").status_code == 503


def test_login_success_failure_and_logout_are_audited_without_secrets(
    client,
    authenticate,
):
    attempted_password = "never-persist-this-password"
    authenticate(False)
    response = client.post(
        "/api/login",
        json={"username": "operator", "password": attempted_password},
    )
    assert response.status_code == 401

    _login(client, authenticate)
    assert client.post("/api/logout").status_code == 204
    events = client.app.state.event_store.query(limit=100, category=EventCategory.SECURITY)
    serialized = json.dumps([event.model_dump(mode="json") for event in events])
    assert attempted_password not in serialized
    assert "gyro_session" not in serialized
    assert not any("token" in event.details for event in events)
    assert {
        "security.login_failed",
        "security.login_succeeded",
        "security.logout",
    }.issubset({event.event_type for event in events})


def test_admin_user_mutation_records_actor(client, authenticate):
    _login(client, authenticate, "admin")
    response = client.post(
        "/api/users/add",
        json={"username": "new-user", "role": "user"},
    )
    assert response.status_code == 201
    events = client.app.state.event_store.query(limit=10, category=EventCategory.OPERATOR)
    assert events[0].event_type == "operator.user_added"
    assert events[0].actor == "admin"
    assert events[0].target == "new-user"


def test_rejected_setpoint_is_audited_without_execution(client, authenticate):
    _login(client, authenticate)
    response = client.post("/api/setpoint")
    assert response.status_code == 503
    events = client.app.state.event_store.query(limit=10, category=EventCategory.COMMAND)
    assert events[0].event_type == "command.rejected"
    assert events[0].actor == "operator"
    assert events[0].target == "setpoint.apply"
    assert events[0].details == {"reason": "hardware_command_execution_unavailable"}
    assert not {"command.sent", "command.acknowledged"}.intersection(
        event.event_type for event in events
    )


def test_event_api_is_bounded_and_supports_pagination_and_filters(client, authenticate):
    authenticate(False)
    assert client.post(
        "/api/login", json={"username": "operator", "password": "invalid"}
    ).status_code == 401
    _login(client, authenticate)
    first = client.get("/api/events", params={"limit": 1, "category": "security"})
    assert first.status_code == 200
    assert len(first.json()["events"]) == 1
    assert first.json()["next_before_id"] is not None
    second = client.get(
        "/api/events",
        params={
            "limit": 1,
            "category": "security",
            "before_id": first.json()["next_before_id"],
        },
    )
    assert second.status_code == 200
    assert all(
        event["id"] < first.json()["events"][0]["id"]
        for event in second.json()["events"]
    )
    assert client.get("/api/events", params={"limit": 201}).status_code == 422


def test_all_phase4_command_capabilities_are_unavailable_and_authenticated(
    client,
    authenticate,
):
    assert client.get("/api/command-capabilities").status_code == 401
    _login(client, authenticate)
    response = client.get("/api/command-capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_available"] is False
    assert len(payload["capabilities"]) == 8
    assert all(capability["available"] is False for capability in payload["capabilities"])
    assert all(capability["blockers"] for capability in payload["capabilities"])

    capabilities = phase4_capabilities().capabilities
    assert all(CommandBlocker.EXECUTION_NOT_IMPLEMENTED in item.blockers for item in capabilities)
    assert all(CommandBlocker.WRITE_NODE_UNRESOLVED in item.blockers for item in capabilities)
    assert all(CommandBlocker.READBACK_UNRESOLVED in item.blockers for item in capabilities)
    assert all(CommandBlocker.ACKNOWLEDGEMENT_UNRESOLVED in item.blockers for item in capabilities)
    assert all(CommandBlocker.PRECONDITIONS_UNRESOLVED in item.blockers for item in capabilities)
    assert all(CommandBlocker.AUTHORIZATION_UNAPPROVED in item.blockers for item in capabilities)
    assert all(CommandBlocker.CONFIRMATION_UNAPPROVED in item.blockers for item in capabilities)

    paths = client.app.openapi()["paths"]
    assert not any(
        fragment in path
        for path in paths
        for fragment in ("/commands", "/reset", "/acknowledge", "/emergency")
    )


def test_command_contract_template_cannot_activate_execution():
    path = Path(__file__).resolve().parents[1] / "config" / "command_contract.example.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    template = CommandContractTemplate.model_validate(payload)
    assert len(template.commands) == 8

    payload["commands"][0]["available"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CommandContractTemplate.model_validate(payload)
