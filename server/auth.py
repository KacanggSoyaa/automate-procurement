"""Admin-created user accounts with JWT sessions in an httpOnly cookie.

Users are stored in ``data/users.json`` (never committed). Passwords are hashed
with bcrypt. Sessions are signed JWTs carried in an httpOnly cookie, so all
``/api`` routes are protected and the browser attaches the token automatically.

The first (admin) account is created with the CLI helper::

    python -m server.auth add-user --username admin --admin

or by setting ``ADMIN_USERNAME`` / ``ADMIN_PASSWORD`` in the environment, which
is bootstrapped automatically on startup when no users exist yet.
"""
import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException

DATA_ROOT = Path("./data")
STORE_PATH = DATA_ROOT / "users.json"

COOKIE_NAME = "ap_session"
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "7"))

# Order of user-editable profile fields (username is the login identifier).
_FIELDS = ("username", "display_name", "role")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _secret() -> str:
    """Signing secret. Prefer AUTH_SECRET; fall back to a persisted random key.

    A random key is generated once and stored so sessions survive restarts on a
    dev machine. In production you should set AUTH_SECRET explicitly.
    """
    explicit = os.environ.get("AUTH_SECRET")
    if explicit:
        return explicit
    key_path = DATA_ROOT / "auth_secret.key"
    try:
        return key_path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    generated = secrets.token_urlsafe(48)
    try:
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(generated, encoding="utf-8")
    except Exception:
        pass
    return generated


class AuthError(HTTPException):
    """401 for any missing/invalid session, in a shape the frontend expects."""

    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(status_code=401, detail=detail)


class UserStore:
    """Thread-safe, file-backed store of user accounts."""

    def __init__(self, path: Path = None):
        self.path = Path(path) if path else STORE_PATH
        self._lock = threading.Lock()
        self._items: List[Dict] = self._read()

    def _read(self) -> List[Dict]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except Exception:
            return []

    def _write(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._items, indent=2), encoding="utf-8")
        except Exception:
            pass

    @staticmethod
    def _hash(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def _public(user: Dict) -> Dict:
        """Strip the password hash before returning a user to callers."""
        return {k: v for k, v in user.items() if k != "password_hash"}

    def list(self) -> List[Dict]:
        with self._lock:
            return [self._public(u) for u in self._items]

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def get(self, user_id: str) -> Optional[Dict]:
        with self._lock:
            user = next((u for u in self._items if u.get("id") == user_id), None)
            return self._public(user) if user else None

    def by_username(self, username: str) -> Optional[Dict]:
        target = (username or "").strip().lower()
        with self._lock:
            return next((u for u in self._items if u.get("username", "").lower() == target), None)

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Return the public user record when the credentials are valid."""
        user = self.by_username(username)
        if not user or not password:
            return None
        if not self._verify(password, user.get("password_hash", "")):
            return None
        return self._public(user)

    def create(self, username: str, password: str, display_name: str = "", role: str = "user") -> Dict:
        """Create a user. Raises ValueError on blank fields or a duplicate name."""
        username = (username or "").strip()
        if not username:
            raise ValueError("Username must not be empty.")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        with self._lock:
            if any(u.get("username", "").lower() == username.lower() for u in self._items):
                raise ValueError("That username already exists.")
            user = {
                "id": uuid.uuid4().hex[:12],
                "username": username,
                "display_name": (display_name or username).strip(),
                "role": "admin" if role == "admin" else "user",
                "password_hash": self._hash(password),
                "created_at": _now(),
            }
            self._items.append(user)
            self._write()
            return self._public(user)

    def set_password(self, user_id: str, password: str) -> Optional[Dict]:
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        with self._lock:
            user = next((u for u in self._items if u.get("id") == user_id), None)
            if user is None:
                return None
            user["password_hash"] = self._hash(password)
            user["updated_at"] = _now()
            self._write()
            return self._public(user)

    def delete(self, user_id: str) -> bool:
        with self._lock:
            before = len(self._items)
            self._items = [u for u in self._items if u.get("id") != user_id]
            removed = len(self._items) != before
            if removed:
                self._write()
            return removed


user_store = UserStore()


def make_token(user: Dict) -> str:
    """Sign a short-lived JWT for a user record."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "role": user.get("role", "user"),
        "iat": now,
        "exp": now + timedelta(days=SESSION_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_token(token: str) -> Optional[Dict]:
    """Decode and validate a session token; returns None when invalid/expired."""
    try:
        return jwt.decode(token, _secret(), algorithms=["HS256"])
    except Exception:
        return None


def current_user(ap_session: Optional[str] = Cookie(default=None)) -> Dict:
    """FastAPI dependency: resolve the session cookie to a live user record."""
    if not ap_session:
        raise AuthError()
    payload = decode_token(ap_session)
    if not payload:
        raise AuthError("Session expired or invalid")
    user = user_store.get(payload.get("sub", ""))
    if not user:
        raise AuthError("User no longer exists")
    return user


def require_admin(user: Dict = Depends(current_user)) -> Dict:
    """FastAPI dependency: like ``current_user`` but requires the admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user


def bootstrap_admin() -> None:
    """Create the initial admin from env vars when the store is empty.

    Set ``ADMIN_USERNAME`` and ``ADMIN_PASSWORD`` to have a usable account on
    first boot without touching the CLI.
    """
    if user_store.count() > 0:
        return
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        return
    try:
        user_store.create(username, password, display_name=username, role="admin")
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover - small CLI helper
    import argparse
    import getpass

    parser = argparse.ArgumentParser(description="Manage Automate Procurement users")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add-user", help="Create a new user")
    p_add.add_argument("--username", required=True)
    p_add.add_argument("--password", help="Omit to be prompted")
    p_add.add_argument("--name", dest="display_name", default="")
    p_add.add_argument("--admin", action="store_true")

    p_pw = sub.add_parser("set-password", help="Reset a user's password")
    p_pw.add_argument("--username", required=True)
    p_pw.add_argument("--password", help="Omit to be prompted")

    sub.add_parser("list-users", help="List all users")

    p_del = sub.add_parser("delete-user", help="Delete a user")
    p_del.add_argument("--username", required=True)

    args = parser.parse_args()

    if args.cmd == "add-user":
        pw = args.password or getpass.getpass("Password: ")
        user = user_store.create(
            args.username, pw, display_name=args.display_name,
            role="admin" if args.admin else "user",
        )
        print(f"created user {user['username']} ({user['role']}) id={user['id']}")
    elif args.cmd == "set-password":
        user = user_store.by_username(args.username)
        if not user:
            raise SystemExit(f"no such user: {args.username}")
        pw = args.password or getpass.getpass("New password: ")
        user_store.set_password(user["id"], pw)
        print(f"password updated for {args.username}")
    elif args.cmd == "list-users":
        for u in user_store.list():
            print(f"{u['id']}  {u['username']:<20} {u['role']}")
    elif args.cmd == "delete-user":
        user = user_store.by_username(args.username)
        if not user:
            raise SystemExit(f"no such user: {args.username}")
        user_store.delete(user["id"])
        print(f"deleted {args.username}")
