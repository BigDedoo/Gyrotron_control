import asyncio
from pathlib import Path

import pytest
from asyncua import ua
from asyncua.crypto.cert_gen import setup_self_signed_certificate
from asyncua.crypto import security_policies
from cryptography.x509.oid import ExtendedKeyUsageOID
from pydantic import SecretStr, ValidationError

from app.core.config import AppSettings, OPCUASettings
from app.models import ConnectionState
from app.opcua.client import OPCUAConnectionError, ReadOnlyOPCUAClient
from app.opcua.node_map import LogicalSignal
from tests.opcua_simulator import LocalOPCUASimulator


def _security_files(tmp_path: Path) -> dict[str, Path]:
    paths = {
        "node_map_path": tmp_path / "nodes.json",
        "client_certificate_path": tmp_path / "client.der",
        "client_private_key_path": tmp_path / "client.key.pem",
        "server_certificate_path": tmp_path / "server.der",
    }
    for path in paths.values():
        if not path.exists():
            path.write_bytes(b"test fixture placeholder")
    return paths


def _settings_values(tmp_path: Path, **overrides) -> dict:
    values = {
        "endpoint_url": "opc.tcp://plc.invalid.test:4840/gyrotron/",
        "connect_timeout_seconds": 1,
        "read_timeout_seconds": 1,
        "monitor_interval_seconds": 1,
        "reconnect_initial_seconds": 1,
        "reconnect_max_seconds": 2,
        "stale_after_seconds": 3,
        "security_policy": "Basic256Sha256",
        "security_mode": "SignAndEncrypt",
        **_security_files(tmp_path),
    }
    values.update(overrides)
    return values


def _settings(tmp_path: Path, **overrides) -> OPCUASettings:
    return OPCUASettings(**_settings_values(tmp_path, **overrides))


def test_simulation_requires_no_opcua_security_configuration(monkeypatch):
    monkeypatch.setenv("APP_MODE", "simulation")
    for name in (
        "OPCUA_ENDPOINT_URL",
        "OPCUA_NODE_MAP_PATH",
        "OPCUA_SECURITY_POLICY",
        "OPCUA_SECURITY_MODE",
        "OPCUA_CLIENT_CERTIFICATE_PATH",
        "OPCUA_CLIENT_PRIVATE_KEY_PATH",
        "OPCUA_SERVER_CERTIFICATE_PATH",
        "OPCUA_USERNAME",
        "OPCUA_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)

    assert AppSettings.from_environment().opcua is None


def test_non_local_none_security_is_rejected(tmp_path: Path):
    with pytest.raises(ValidationError, match="insecure OPC UA requires"):
        _settings(
            tmp_path,
            security_policy="None",
            security_mode="None",
            client_certificate_path=None,
            client_private_key_path=None,
            server_certificate_path=None,
        )


def test_missing_security_policy_is_rejected(tmp_path: Path):
    with pytest.raises(ValidationError, match="must be explicitly configured"):
        _settings(tmp_path, security_policy="")


def test_insecure_or_unsupported_policy_is_rejected(tmp_path: Path):
    with pytest.raises(ValidationError, match="OPCUA_SECURITY_POLICY must be one of"):
        _settings(tmp_path, security_policy="Basic128Rsa15")


def test_sign_without_encryption_is_rejected(tmp_path: Path):
    with pytest.raises(ValidationError, match="must be SignAndEncrypt"):
        _settings(tmp_path, security_mode="Sign")


def test_missing_trusted_server_identity_is_rejected(tmp_path: Path):
    with pytest.raises(ValidationError, match="trusted server certificate"):
        _settings(tmp_path, server_certificate_path=None)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("client_certificate_path", "client certificate"),
        ("client_private_key_path", "client private key"),
    ],
)
def test_missing_required_client_identity_file_is_rejected(
    tmp_path: Path,
    field: str,
    message: str,
):
    with pytest.raises(ValidationError, match=message):
        _settings(tmp_path, **{field: None})


def test_incomplete_client_certificate_key_pair_is_rejected(tmp_path: Path):
    missing_key = tmp_path / "missing-client.key.pem"
    with pytest.raises(ValidationError, match="client private key path"):
        _settings(tmp_path, client_private_key_path=missing_key)


def test_username_password_over_insecure_channel_is_rejected(tmp_path: Path):
    with pytest.raises(ValidationError, match="username/password requires SignAndEncrypt"):
        _settings(
            tmp_path,
            endpoint_url="opc.tcp://127.0.0.1:4840/test/",
            security_policy="None",
            security_mode="None",
            client_certificate_path=None,
            client_private_key_path=None,
            server_certificate_path=None,
            allow_insecure_localhost=True,
            username="operator",
            password=SecretStr("not-logged"),
        )


def test_valid_secure_configuration_is_accepted(tmp_path: Path):
    settings = _settings(tmp_path)
    assert settings.security_policy == "Basic256Sha256"
    assert settings.security_mode == "SignAndEncrypt"
    assert settings.server_certificate_path is not None


@pytest.mark.parametrize(
    "endpoint",
    [
        "opc.tcp://127.0.0.1:4840/test/",
        "opc.tcp://localhost:4840/test/",
        "opc.tcp://[::1]:4840/test/",
    ],
    ids=["ipv4", "localhost", "ipv6"],
)
def test_explicit_insecure_loopback_configuration_is_accepted(
    tmp_path: Path,
    endpoint: str,
):
    settings = _settings(
        tmp_path,
        endpoint_url=endpoint,
        security_policy="None",
        security_mode="None",
        client_certificate_path=None,
        client_private_key_path=None,
        server_certificate_path=None,
        allow_insecure_localhost=True,
    )
    assert settings.allow_insecure_localhost is True


@pytest.mark.parametrize(
    "endpoint",
    [
        "opc.tcp://192.168.1.10:4840/test/",
        "opc.tcp://plc.invalid.test:4840/test/",
    ],
    ids=["private-lan", "hostname"],
)
def test_insecure_localhost_override_rejects_non_loopback_endpoint(
    tmp_path: Path,
    endpoint: str,
):
    with pytest.raises(ValidationError, match="loopback endpoints only"):
        _settings(
            tmp_path,
            endpoint_url=endpoint,
            security_policy="None",
            security_mode="None",
            client_certificate_path=None,
            client_private_key_path=None,
            server_certificate_path=None,
            allow_insecure_localhost=True,
        )


class RecordingClient:
    def __init__(self, *, fail_connect: bool = False) -> None:
        self.fail_connect = fail_connect
        self.security_calls: list[tuple[tuple, dict]] = []
        self.user: str | None = None
        self.password: str | None = None
        self.connect_calls = 0
        self.disconnect_calls = 0

    async def set_security(self, *args, **kwargs) -> None:
        self.security_calls.append((args, kwargs))

    def set_user(self, username: str) -> None:
        self.user = username

    def set_password(self, password: str) -> None:
        self.password = password

    async def connect(self) -> None:
        self.connect_calls += 1
        if self.fail_connect:
            raise RuntimeError("secure connection rejected")

    async def disconnect(self) -> None:
        self.disconnect_calls += 1


def test_client_applies_typed_secure_profile_and_credentials(tmp_path: Path):
    async def scenario() -> None:
        settings = _settings(
            tmp_path,
            username="operator",
            password=SecretStr("transport-protected"),
            client_private_key_password=SecretStr("key-secret"),
        )
        transport = RecordingClient()
        client = ReadOnlyOPCUAClient(settings, client_factory=lambda _url, _timeout: transport)
        try:
            await client.connect()
            assert client.connection_state == ConnectionState.CONNECTED
            assert len(transport.security_calls) == 1
            args, kwargs = transport.security_calls[0]
            assert args == (
                security_policies.SecurityPolicyBasic256Sha256,
                settings.client_certificate_path,
                settings.client_private_key_path,
            )
            assert kwargs == {
                "private_key_password": "key-secret",
                "server_certificate": settings.server_certificate_path,
                "mode": ua.MessageSecurityMode.SignAndEncrypt,
            }
            assert transport.user == "operator"
            assert transport.password == "transport-protected"
            assert transport.connect_calls == 1
        finally:
            await client.disconnect()

    asyncio.run(scenario())


def test_failed_secure_attempts_never_fall_back_or_change_profile(tmp_path: Path):
    async def scenario() -> None:
        settings = _settings(tmp_path)
        attempts: list[RecordingClient] = []

        def factory(_url: str, _timeout: float) -> RecordingClient:
            transport = RecordingClient(fail_connect=True)
            attempts.append(transport)
            return transport

        client = ReadOnlyOPCUAClient(settings, client_factory=factory)
        for _ in range(2):
            with pytest.raises(OPCUAConnectionError):
                await client.connect()

        assert len(attempts) == 2
        for transport in attempts:
            assert transport.connect_calls == 1
            assert len(transport.security_calls) == 1
            args, kwargs = transport.security_calls[0]
            assert args[0] is security_policies.SecurityPolicyBasic256Sha256
            assert kwargs["mode"] == ua.MessageSecurityMode.SignAndEncrypt
            assert kwargs["server_certificate"] == settings.server_certificate_path

    asyncio.run(scenario())


def test_insecure_loopback_client_does_not_apply_credentials_or_security(tmp_path: Path):
    async def scenario() -> None:
        settings = _settings(
            tmp_path,
            endpoint_url="opc.tcp://127.0.0.1:4840/test/",
            security_policy="None",
            security_mode="None",
            client_certificate_path=None,
            client_private_key_path=None,
            server_certificate_path=None,
            allow_insecure_localhost=True,
        )
        transport = RecordingClient()
        client = ReadOnlyOPCUAClient(settings, client_factory=lambda _url, _timeout: transport)
        try:
            await client.connect()
            assert transport.security_calls == []
            assert transport.user is None
            assert transport.password is None
        finally:
            await client.disconnect()

    asyncio.run(scenario())


async def _generate_test_identity(
    directory: Path,
    name: str,
    usage,
) -> tuple[Path, Path]:
    key_path = directory / f"{name}.key.pem"
    certificate_path = directory / f"{name}.der"
    await setup_self_signed_certificate(
        key_path,
        certificate_path,
        f"urn:gyrotron:test:{name}",
        "localhost",
        [usage],
        {"organizationName": "Gyrotron test only"},
    )
    return certificate_path, key_path


def test_secure_loopback_server_accepts_pinned_identity_and_rejects_wrong_pin(
    tmp_path: Path,
):
    async def scenario() -> None:
        server_certificate, server_key = await _generate_test_identity(
            tmp_path,
            "server",
            ExtendedKeyUsageOID.SERVER_AUTH,
        )
        wrong_server_certificate, _ = await _generate_test_identity(
            tmp_path,
            "wrong-server",
            ExtendedKeyUsageOID.SERVER_AUTH,
        )
        client_certificate, client_key = await _generate_test_identity(
            tmp_path,
            "client",
            ExtendedKeyUsageOID.CLIENT_AUTH,
        )
        node_map_path = tmp_path / "nodes.json"
        node_map_path.write_text("{}", encoding="utf-8")
        simulator = LocalOPCUASimulator(
            security_certificate_path=server_certificate,
            security_private_key_path=server_key,
        )
        await simulator.start()
        try:
            secure_settings = _settings(
                tmp_path,
                endpoint_url=simulator.endpoint_url,
                node_map_path=node_map_path,
                client_certificate_path=client_certificate,
                client_private_key_path=client_key,
                server_certificate_path=server_certificate,
            )
            client = ReadOnlyOPCUAClient(secure_settings)
            try:
                await client.connect()
                values = await client.read_signals(simulator.node_map().signals)
                assert values[LogicalSignal.ION_V].value == pytest.approx(4.5)
            finally:
                await client.disconnect()

            wrong_pin_client = ReadOnlyOPCUAClient(
                secure_settings.model_copy(
                    update={"server_certificate_path": wrong_server_certificate}
                )
            )
            with pytest.raises(OPCUAConnectionError):
                await wrong_pin_client.connect()
            assert wrong_pin_client.connection_state == ConnectionState.ERROR
            await wrong_pin_client.disconnect()
        finally:
            await simulator.stop()

    asyncio.run(scenario())
