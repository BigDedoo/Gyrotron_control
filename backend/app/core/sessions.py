import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.models import UserRole


@dataclass(frozen=True)
class ApplicationSession:
    token: str
    username: str
    role: UserRole
    expires_at: datetime


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ApplicationSession] = {}
        self._lock = threading.RLock()

    def create(
        self, username: str, role: UserRole, ttl_seconds: int | None = None
    ) -> ApplicationSession:
        ttl = ttl_seconds if ttl_seconds is not None else get_settings().session_ttl_seconds
        now = datetime.now(timezone.utc)
        session = ApplicationSession(
            token=secrets.token_urlsafe(32),
            username=username,
            role=role,
            expires_at=now + timedelta(seconds=ttl),
        )
        with self._lock:
            self._remove_expired(now)
            self._sessions[session.token] = session
        return session

    def get(self, token: str | None) -> ApplicationSession | None:
        if not token:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            self._remove_expired(now)
            return self._sessions.get(token)

    def destroy(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(token, None)

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def _remove_expired(self, now: datetime) -> None:
        expired = [token for token, session in self._sessions.items() if session.expires_at <= now]
        for token in expired:
            self._sessions.pop(token, None)


session_manager = SessionManager()


def get_current_session(request: Request) -> ApplicationSession:
    cookie_name = get_settings().session_cookie_name
    token = request.cookies.get(cookie_name)
    session = session_manager.get(token)
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    # Resolve authorization from the server-side user store on every request so
    # removing or demoting a user takes effect without waiting for session expiry.
    from app.core.users import user_manager

    current_role = user_manager.get_role(session.username)
    if current_role is None:
        session_manager.destroy(token)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session user is no longer authorized")
    if current_role is not session.role:
        return ApplicationSession(
            token=session.token,
            username=session.username,
            role=current_role,
            expires_at=session.expires_at,
        )
    return session


def require_admin(
    session: ApplicationSession = Depends(get_current_session),
) -> ApplicationSession:
    if session.role is not UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
    return session
