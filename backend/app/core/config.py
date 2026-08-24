import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

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

    @classmethod
    def from_environment(cls) -> "AppSettings":
        origins = tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:5174"
            ).split(",")
            if origin.strip()
        )
        return cls(
            app_mode=os.getenv("APP_MODE", "simulation").strip().lower(),
            cors_origins=origins,
            ldap_server_host=os.getenv("LDAP_SERVER_HOST", "ccsvad05.in2p3.fr").strip(),
            ldap_domain=os.getenv("LDAP_DOMAIN", "grenoble.in2p3.fr").strip(),
            ldap_port=int(os.getenv("LDAP_PORT", "636")),
            ldap_use_ssl=_environment_bool("LDAP_USE_SSL", True),
            ldap_timeout_seconds=float(os.getenv("LDAP_TIMEOUT_SECONDS", "5")),
            session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "gyro_session").strip(),
            session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "28800")),
            session_cookie_secure=_environment_bool("SESSION_COOKIE_SECURE", False),
        )


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings.from_environment()
