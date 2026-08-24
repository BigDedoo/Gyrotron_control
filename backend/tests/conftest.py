from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import endpoints
from app.core import users as users_module
from app.core.sessions import session_manager
from app.core.users import UserManager
from app.main import app
from app.models import UserRole


@pytest.fixture(autouse=True)
def clear_sessions():
    session_manager.clear()
    yield
    session_manager.clear()


@pytest.fixture
def user_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> UserManager:
    manager = UserManager(
        tmp_path / "users.json",
        default_users={"admin": UserRole.ADMIN, "operator": UserRole.USER},
    )
    monkeypatch.setattr(users_module, "user_manager", manager)
    monkeypatch.setattr(endpoints, "user_manager", manager)
    return manager


@pytest.fixture
def client(user_manager: UserManager) -> TestClient:
    del user_manager
    return TestClient(app)


@pytest.fixture
def authenticate(monkeypatch: pytest.MonkeyPatch):
    def set_result(result: bool) -> None:
        monkeypatch.setattr(endpoints, "authenticate_user", lambda _username, _password: result)

    return set_result
