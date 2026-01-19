import json
import os
import logging
from typing import Dict, List, Union

logger = logging.getLogger(__name__)

DATA_FILE = "data/users.json"

class UserManager:
    def __init__(self):
        self._ensure_data_dir()
        self.users: Dict[str, str] = self._load_users()

    def _ensure_data_dir(self):
        if not os.path.exists("data"):
            os.makedirs("data")

    def _load_users(self) -> Dict[str, str]:
        if not os.path.exists(DATA_FILE):
            # Default initialization: gemond is admin
            default_users = {"gemond": "admin"}
            self._save_users(default_users)
            return default_users
        
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
                
            # MIGRATION: If data is a list (legacy), convert to dict
            if isinstance(data, list):
                logger.info("Migrating legacy user list to RBAC dict...")
                new_data = {}
                for u in data:
                    # Default everyone to 'user', force gemond to 'admin'
                    role = "admin" if u == "gemond" else "user"
                    new_data[u] = role
                self._save_users(new_data)
                return new_data
            
            return data
            
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {"gemond": "admin"}

    def _save_users(self, users: Dict[str, str]):
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(users, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving users: {e}")

    def is_allowed(self, username: str) -> bool:
        # Check against simple match, UPN, or DOMAIN\user
        return self.get_role(username) is not None

    def get_role(self, username: str) -> Union[str, None]:
        # exact match
        if username in self.users:
            return self.users[username]
            
        # user@domain
        if "@" in username:
            short = username.split("@")[0]
            if short in self.users:
                return self.users[short]

        # domain\user
        if "\\" in username:
            short = username.split("\\")[1]
            if short in self.users:
                return self.users[short]
                
        return None

    def get_users(self) -> List[Dict[str, str]]:
        # Return list of objects for frontend API
        return [{"username": u, "role": r} for u, r in self.users.items()]

    def add_user(self, username: str, role: str = "user"):
        self.users[username] = role
        self._save_users(self.users)

    def update_role(self, username: str, role: str):
        if username in self.users:
            self.users[username] = role
            self._save_users(self.users)

    def remove_user(self, username: str):
        if username in self.users:
            del self.users[username]
            self._save_users(self.users)

# Singleton instance
user_manager = UserManager()
