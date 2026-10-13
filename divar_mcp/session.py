"""Session manager for Divar MCP.
Handles persistent auth token and login state.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

# Save session in user home or local workspace
USER_HOME = Path.home()
SESSION_DIR = USER_HOME / ".divar_mcp"
SESSION_FILE = SESSION_DIR / "session.json"
WORKSPACE_SESSION_FILE = Path(__file__).resolve().parent.parent / "divar_session.json"


def _get_target_file() -> Path:
    try:
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        return SESSION_FILE
    except Exception:
        return WORKSPACE_SESSION_FILE


def load_session() -> dict:
    for target in (SESSION_FILE, WORKSPACE_SESSION_FILE):
        if target.exists():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
    return {}


def save_session(data: dict) -> None:
    target = _get_target_file()
    try:
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        # Fallback to workspace session
        with open(WORKSPACE_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def get_token() -> str | None:
    session = load_session()
    return session.get("token")


def set_token(token: str, phone: str | None = None, extra: dict | None = None) -> dict:
    session = load_session()
    session["token"] = token
    if phone:
        session["phone"] = phone
    session["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if extra:
        session.update(extra)
    save_session(session)
    return session


def clear_session() -> None:
    for target in (SESSION_FILE, WORKSPACE_SESSION_FILE):
        if target.exists():
            try:
                os.remove(target)
            except Exception:
                pass


def is_authenticated() -> bool:
    return bool(get_token())


def get_cookies() -> str | None:
    session = load_session()
    return session.get("cookies")


def set_cookies(cookies: str) -> None:
    session = load_session()
    session["cookies"] = cookies
    save_session(session)


def get_session_info() -> dict:
    session = load_session()
    token = session.get("token")
    masked_token = f"{token[:6]}...{token[-4:]}" if token and len(token) > 10 else (token or None)
    return {
        "authenticated": bool(token or session.get("cookies")),
        "phone": session.get("phone"),
        "token_masked": masked_token,
        "has_cookies": bool(session.get("cookies")),
        "updated_at": session.get("updated_at"),
    }
