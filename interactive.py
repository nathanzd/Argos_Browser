from __future__ import annotations

import threading
import uuid
from typing import Any

from config import settings
from exceptions import SessionNotFoundError
from sandbox import ALLOWED_NAMES, _safe_builtins
from utils import get_logger

logger = get_logger(__name__)


class InteractiveSession:
    def __init__(self, session_id: str) -> None:
        self._id: str = session_id
        self._scope: dict[str, Any] = {
            **ALLOWED_NAMES,
            "__builtins__": _safe_builtins(),
        }
        self._created_at: float = 0.0
        self._command_count: int = 0
        self._lock: threading.Lock = threading.Lock()

    @property
    def id(self) -> str:
        return self._id

    @property
    def scope(self) -> dict[str, Any]:
        return self._scope

    @property
    def command_count(self) -> int:
        return self._command_count

    def inject_driver(self, driver: Any) -> None:
        with self._lock:
            self._scope["driver"] = driver

    def get_namespace(self) -> dict[str, Any]:
        return self._scope

    def increment_commands(self) -> None:
        with self._lock:
            self._command_count += 1

    def cleanup(self) -> None:
        keys_to_remove = [
            k for k in self._scope if k not in ALLOWED_NAMES and k != "__builtins__"
        ]
        for k in keys_to_remove:
            del self._scope[k]


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, InteractiveSession] = {}
        self._lock: threading.Lock = threading.Lock()

    @property
    def active_sessions(self) -> list[str]:
        with self._lock:
            return list(self._sessions.keys())

    def create_session(self) -> InteractiveSession:
        session_id = str(uuid.uuid4())
        session = InteractiveSession(session_id)
        with self._lock:
            self._sessions[session_id] = session
        logger.info("Session created: %s", session_id)
        return session

    def get_session(self, session_id: str) -> InteractiveSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            raise SessionNotFoundError(session_id)
        session.cleanup()
        logger.info("Session deleted: %s", session_id)

    def inject_driver_to_all(self, driver: Any) -> None:
        with self._lock:
            for session in self._sessions.values():
                session.inject_driver(driver)

    def cleanup_all(self) -> None:
        with self._lock:
            for session in self._sessions.values():
                session.cleanup()
            self._sessions.clear()
