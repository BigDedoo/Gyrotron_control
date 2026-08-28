import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from app.models import AppMode


BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")


def _environment_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required when APP_MODE=opcua_readonly")
    return value


def _configured_path(name: str, *, required: bool = False) -> Path | None:
    raw = _required_environment(name) if required else os.getenv(name, "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    return path.resolve()


class OPCUASettings(BaseModel):
    endpoint_url: str = Field(min_length=1, max_length=2048)
    connect_timeout_seconds: float = Field(gt=0, le=60)
    read_timeout_seconds: float = Field(gt=0, le=60)
    monitor_interval_seconds: float = Field(gt=0, le=300)
    reconnect_initial_seconds: float = Field(gt=0, le=300)
    reconnect_max_seconds: float = Field(gt=0, le=3600)
    stale_after_seconds: float = Field(gt=0, le=3600)
    node_map_path: Path
    security_policy: str
    security_mode: str
    client_certificate_path: Path | None = None
    client_private_key_path: Path | None = None
    client_private_key_password: SecretStr | None = None
    server_certificate_path: Path | None = None
    username: str | None = Field(default=None, max_length=256)
    password: SecretStr | None = None
    allow_insecure_localhost: bool = False

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        endpoint = value.strip()
        if any(marker in endpoint.upper() for marker in ("TODO", "REPLACE_ME", "CONFIGURE_ME")):
            raise ValueError("placeholder OPC UA endpoints are not permitted")
        parsed = urlsplit(endpoint)
        if parsed.scheme != "opc.tcp" or not parsed.hostname or parsed.port is None:
            raise ValueError("OPCUA_ENDPOINT_URL must be an opc.tcp URL with an explicit port")
        if parsed.username or parsed.password:
            raise ValueError("OPC UA credentials must not be embedded in the endpoint URL")
        return endpoint

    @field_validator("security_policy")
    @classmethod
    def validate_security_policy(cls, value: str) -> str:
        value = value.strip()
        allowed = {
            "None",
            "Basic256Sha256",
            "Aes128Sha256RsaOaep",
            "Aes256Sha256RsaPss",
        }
        if value and value not in allowed:
            raise ValueError(f"OPCUA_SECURITY_POLICY must be one of {sorted(allowed)}")
        return value

    @field_validator("security_mode")
    @classmethod
    def validate_security_mode(cls, value: str) -> str:
        value = value.strip()
        allowed = {"None", "Sign", "SignAndEncrypt"}
        if value and value not in allowed:
            raise ValueError(f"OPCUA_SECURITY_MODE must be one of {sorted(allowed)}")
        return value

    @model_validator(mode="after")
    def validate_combination(self) -> "OPCUASettings":
        if not self.node_map_path.is_file():
            raise ValueError("OPCUA_NODE_MAP_PATH must reference an existing file")
        if self.reconnect_max_seconds < self.reconnect_initial_seconds:
            raise ValueError("OPCUA_RECONNECT_MAX_SECONDS must be >= the initial reconnect delay")
        if self.stale_after_seconds <= self.monitor_interval_seconds * 2:
            raise ValueError(
                "OPCUA_STALE_AFTER_SECONDS must exceed twice the monitor interval"
            )

        if (self.username is None) != (self.password is None):
            raise ValueError("OPCUA_USERNAME and OPCUA_PASSWORD must be configured together")

        if not self.security_policy:
            raise ValueError("OPCUA_SECURITY_POLICY must be explicitly configured")
        if not self.security_mode:
            raise ValueError("OPCUA_SECURITY_MODE must be explicitly configured")

        insecure = self.security_policy == "None" and self.security_mode == "None"
        if (self.security_policy == "None") != (self.security_mode == "None"):
            raise ValueError("secure OPC UA requires both a secure policy and security mode")

        if insecure:
            endpoint_host = (urlsplit(self.endpoint_url).hostname or "").lower()
            if not self.allow_insecure_localhost:
                raise ValueError(
                    "insecure OPC UA requires OPCUA_ALLOW_INSECURE_LOCALHOST=true"
                )
            if endpoint_host not in {"127.0.0.1", "::1", "localhost"}:
                raise ValueError(
                    "OPCUA_ALLOW_INSECURE_LOCALHOST permits loopback endpoints only"
                )
            if any(
                value is not None
                for value in (
                    self.client_certificate_path,
                    self.client_private_key_path,
                    self.client_private_key_password,
                    self.server_certificate_path,
                )
            ):
                raise ValueError(
                    "certificate and private-key settings require secure OPC UA"
                )
            if self.username is not None:
                raise ValueError("OPC UA username/password requires SignAndEncrypt")
            return self

        if self.security_policy == "None":
            raise ValueError("secure OPC UA requires an explicit secure policy")
        if self.security_mode != "SignAndEncrypt":
            raise ValueError("OPC UA security mode must be SignAndEncrypt")

        required_files = (
            (self.client_certificate_path, "client certificate"),
            (self.client_private_key_path, "client private key"),
            (self.server_certificate_path, "trusted server certificate"),
        )
        for path, label in required_files:
            if path is None:
                raise ValueError(f"secure OPC UA requires a {label}")
            if not path.is_file():
                raise ValueError(f"OPC UA {label} path must reference an existing file")
        return self

    @classmethod
    def from_environment(cls) -> "OPCUASettings":
        username = os.getenv("OPCUA_USERNAME", "").strip() or None
        password = os.getenv("OPCUA_PASSWORD") if username else None
        key_password = os.getenv("OPCUA_CLIENT_PRIVATE_KEY_PASSWORD")
        return cls(
            endpoint_url=_required_environment("OPCUA_ENDPOINT_URL"),
            connect_timeout_seconds=float(os.getenv("OPCUA_CONNECT_TIMEOUT_SECONDS", "5")),
            read_timeout_seconds=float(os.getenv("OPCUA_READ_TIMEOUT_SECONDS", "3")),
            monitor_interval_seconds=float(os.getenv("OPCUA_MONITOR_INTERVAL_SECONDS", "1")),
            reconnect_initial_seconds=float(os.getenv("OPCUA_RECONNECT_INITIAL_SECONDS", "1")),
            reconnect_max_seconds=float(os.getenv("OPCUA_RECONNECT_MAX_SECONDS", "30")),
            stale_after_seconds=float(os.getenv("OPCUA_STALE_AFTER_SECONDS", "5")),
            node_map_path=_configured_path("OPCUA_NODE_MAP_PATH", required=True),
            security_policy=os.getenv("OPCUA_SECURITY_POLICY", "").strip(),
            security_mode=os.getenv("OPCUA_SECURITY_MODE", "").strip(),
            client_certificate_path=_configured_path("OPCUA_CLIENT_CERTIFICATE_PATH"),
            client_private_key_path=_configured_path("OPCUA_CLIENT_PRIVATE_KEY_PATH"),
            client_private_key_password=SecretStr(key_password) if key_password else None,
            server_certificate_path=_configured_path("OPCUA_SERVER_CERTIFICATE_PATH"),
            username=username,
            password=SecretStr(password) if password is not None else None,
            allow_insecure_localhost=_environment_bool(
                "OPCUA_ALLOW_INSECURE_LOCALHOST", False
            ),
        )


class AppSettings(BaseModel):
    app_mode: AppMode
    cors_origins: tuple[str, ...]
    ldap_server_host: str = Field(min_length=1)
    ldap_domain: str = Field(min_length=1)
    ldap_port: int = Field(ge=1, le=65535)
    ldap_use_ssl: bool
    ldap_timeout_seconds: float = Field(gt=0, le=60)
    session_cookie_name: str = Field(min_length=1, max_length=64)
    session_ttl_seconds: int = Field(ge=300, le=86400)
    session_cookie_secure: bool
    simulation_problem_cycle_seconds: float = Field(default=900.0, ge=30.0, le=86400.0)
    event_db_path: Path = (BACKEND_ROOT / "data" / "events.sqlite3").resolve()
    opcua: OPCUASettings | None = None

    @model_validator(mode="after")
    def validate_mode_configuration(self) -> "AppSettings":
        if self.app_mode == AppMode.OPCUA_READONLY and self.opcua is None:
            raise ValueError("OPC UA configuration is required in opcua_readonly mode")
        if self.app_mode == AppMode.SIMULATION and self.opcua is not None:
            raise ValueError("simulation mode must not initialize OPC UA configuration")
        return self

    @classmethod
    def from_environment(cls) -> "AppSettings":
        app_mode = os.getenv("APP_MODE", "simulation").strip().lower()
        origins = tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:5174"
            ).split(",")
            if origin.strip()
        )
        return cls(
            app_mode=app_mode,
            cors_origins=origins,
            ldap_server_host=os.getenv("LDAP_SERVER_HOST", "ccsvad05.in2p3.fr").strip(),
            ldap_domain=os.getenv("LDAP_DOMAIN", "grenoble.in2p3.fr").strip(),
            ldap_port=int(os.getenv("LDAP_PORT", "636")),
            ldap_use_ssl=_environment_bool("LDAP_USE_SSL", True),
            ldap_timeout_seconds=float(os.getenv("LDAP_TIMEOUT_SECONDS", "5")),
            session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "gyro_session").strip(),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "28800")),
            session_cookie_secure=_environment_bool("SESSION_COOKIE_SECURE", False),
            simulation_problem_cycle_seconds=float(
                os.getenv("SIMULATION_PROBLEM_CYCLE_SECONDS", "900")
            ),
            event_db_path=(
                _configured_path("EVENT_DB_PATH")
                or (BACKEND_ROOT / "data" / "events.sqlite3").resolve()
            ),
            opcua=OPCUASettings.from_environment()
            if app_mode == AppMode.OPCUA_READONLY.value
            else None,
        )


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings.from_environment()
