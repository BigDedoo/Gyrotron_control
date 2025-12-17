import json
import os
from typing import List

DATA_FILE = "data/users.json"

class UserManager:
    def __init__(self):
        self._ensure_data_dir()
        self.users = self._load_users()

    def _ensure_data_dir(self):
        if not os.path.exists("data"):
            os.makedirs("data")

    def _load_users(self) -> List[str]:
        if not os.path.exists(DATA_FILE):
            # Default initialization to prevent lockout
            default_users = ["gemond"]
            self._save_users(default_users)
            return default_users
        
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading users: {e}")
            return ["gemond"]

    def _save_users(self, users: List[str]):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(users, f, indent=2)
        except Exception as e:
            print(f"Error saving users: {e}")

    def is_allowed(self, username: str) -> bool:
        # Check if username (or short username) is in the list
        # We can be lenient: if stored is "gemond" and input is "gemond@grenoble...", we might want to check
        # For now, simplistic exact match or "contains" logic might be needed depending on what comes from LDAP.
        # Let's clean the username to just the 'user' part for comparison if we want to be flexible,
        # OR force the admin to type the full thing.
        # Let's assume we match against the 'short' login name (sAMAccountName style) or full UPN.
        
        # Normalize: check if exact match exists
        if username in self.users:
            return True
        
        # If username is "user@domain.fr", check if "user" is in list
        if "@" in username:
            short_name = username.split("@")[0]
            if short_name in self.users:
                return True
                
        # If username is "DOMAIN\user", check if "user" is in list
        if "\\" in username:
            short_name = username.split("\\")[1]
            if short_name in self.users:
                return True
                
        return False

    def get_users(self) -> List[str]:
        return self.users

    def add_user(self, username: str):
        if username not in self.users:
            self.users.append(username)
            self._save_users(self.users)

    def remove_user(self, username: str):
        if username in self.users:
            self.users.remove(username)
            self._save_users(self.users)

# Singleton instance
user_manager = UserManager()
