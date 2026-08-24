import json
import os
import tempfile
import threading
from pathlib import Path

from app.models import UserRecord, UserRole


DEFAULT_DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "users.json"


class UserManagementError(Exception):
    pass


class UserStorageError(UserManagementError):
    pass


class UserAlreadyExists(UserManagementError):
    pass


class UserNotFound(UserManagementError):
    pass


class LastAdministratorError(UserManagementError):
    pass


class UserManager:
    def __init__(
        self,
        data_file: Path | None = None,
        default_users: dict[str, UserRole] | None = None,
    ) -> None:
        self.data_file = (data_file or DEFAULT_DATA_FILE).resolve()
        self._default_users = default_users or {"gemond": UserRole.ADMIN}
        self._lock = threading.RLock()
        self.users = self._load_users()

    def _load_users(self) -> dict[str, UserRole]:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_file.exists():
            self._save_users(self._default_users)
            return dict(self._default_users)

        try:
            with self.data_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("user store must contain an object")
            return {str(username): UserRole(role) for username, role in data.items()}
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise UserStorageError(f"Unable to load user store: {exc}") from exc

    def _save_users(self, users: dict[str, UserRole]) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.data_file.parent,
                prefix=f".{self.data_file.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump({name: role.value for name, role in users.items()}, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.data_file)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise UserStorageError(f"Unable to save user store: {exc}") from exc

    @staticmethod
    def _short_identity(username: str) -> str:
        short = username.strip()
        if "\\" in short:
            short = short.rsplit("\\", 1)[-1]
        if "@" in short:
            short = short.split("@", 1)[0]
        return short.casefold()

    def get_role(self, username: str) -> UserRole | None:
        target = self._short_identity(username)
        with self._lock:
            for stored_username, role in self.users.items():
                if self._short_identity(stored_username) == target:
                    return role
        return None

    def get_users(self) -> list[UserRecord]:
        with self._lock:
            return [
                UserRecord(username=username, role=role)
                for username, role in sorted(self.users.items(), key=lambda item: item[0].casefold())
            ]

    def add_user(self, username: str, role: UserRole) -> None:
        with self._lock:
            if self.get_role(username) is not None:
                raise UserAlreadyExists(f"User {username} already exists")
            updated = dict(self.users)
            updated[username] = role
            self._save_users(updated)
            self.users = updated

    def update_role(self, username: str, role: UserRole) -> None:
        with self._lock:
            stored_username = self._find_stored_username(username)
            if stored_username is None:
                raise UserNotFound(f"User {username} was not found")
            if self.users[stored_username] is UserRole.ADMIN and role is not UserRole.ADMIN:
                self._ensure_another_admin(stored_username)
            updated = dict(self.users)
            updated[stored_username] = role
            self._save_users(updated)
            self.users = updated

    def remove_user(self, username: str) -> None:
        with self._lock:
            stored_username = self._find_stored_username(username)
            if stored_username is None:
                raise UserNotFound(f"User {username} was not found")
            if self.users[stored_username] is UserRole.ADMIN:
                self._ensure_another_admin(stored_username)
            updated = dict(self.users)
            del updated[stored_username]
            self._save_users(updated)
            self.users = updated

    def _find_stored_username(self, username: str) -> str | None:
        target = self._short_identity(username)
        return next(
            (
                stored_username
                for stored_username in self.users
                if self._short_identity(stored_username) == target
            ),
            None,
        )

    def _ensure_another_admin(self, excluded_username: str) -> None:
        if not any(
            role is UserRole.ADMIN and username != excluded_username
            for username, role in self.users.items()
        ):
            raise LastAdministratorError("The last administrator cannot be removed or demoted")


user_manager = UserManager()
