import logging
import math

from ldap3 import ALL, Connection, Server

from app.core.config import get_settings


logger = logging.getLogger(__name__)


def _ldap_receive_timeout(seconds: float) -> int:
    """ldap3's Linux SO_RCVTIMEO packing requires whole seconds."""
    return max(1, math.ceil(seconds))


def authenticate_user(username: str, password: str) -> bool:
    if not username or not password:
        return False

    settings = get_settings()
    if "\\" in username or "@" in username:
        user_dn = username
    else:
        user_dn = f"{username}@{settings.ldap_domain}"

    try:
        server = Server(
            settings.ldap_server_host,
            port=settings.ldap_port,
            use_ssl=settings.ldap_use_ssl,
            get_info=ALL,
            connect_timeout=settings.ldap_timeout_seconds,
        )
        connection = Connection(
            server,
            user=user_dn,
            password=password,
            auto_bind=True,
            receive_timeout=_ldap_receive_timeout(settings.ldap_timeout_seconds),
        )
        connection.unbind()
        return True
    except Exception as exc:
        logger.warning("LDAP authentication failed for %s: %s", user_dn, exc)
        return False
