def test_diagnostics_is_authenticated_read_only_and_safe_in_simulation(client, authenticate):
    assert client.get("/api/opcua-diagnostics").status_code == 401
    assert client.post("/api/opcua-diagnostics").status_code == 405
    authenticate(True)
    assert client.post("/api/login", json={"username": "operator", "password": "valid"}).status_code == 200
    response = client.get("/api/opcua-diagnostics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"] == "simulation"
    assert payload["telemetry_capability"] == "simulated"
    assert payload["plc_command_capability"] == "unsupported_disabled"
    assert payload["read_only"] is True
    assert payload["signals"] == []
    serialized = response.text.casefold()
    assert "password" not in serialized
    assert "private_key" not in serialized
    assert "token" not in serialized
