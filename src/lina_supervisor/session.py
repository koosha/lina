"""Session models and in-memory store. Pluggable backend via SessionStore Protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from lina_core.caller import CallerContext


@dataclass
class Session:
    session_id: str
    user_id: str
    caller: CallerContext
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity: datetime = field(default_factory=lambda: datetime.now(UTC))
    worker_call_count_total: int = 0


class SessionStore(Protocol):
    def get_or_create(
        self,
        *,
        session_id: str,
        user_id: str,
        caller: CallerContext,
    ) -> Session: ...

    def append_message(self, *, session_id: str, message: dict[str, Any]) -> None: ...

    def update_caller(self, *, session_id: str, caller: CallerContext) -> None: ...


class InMemorySessionStore:
    """Default v1 backend. Replace by subclassing the Protocol for durability."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get_or_create(
        self,
        *,
        session_id: str,
        user_id: str,
        caller: CallerContext,
    ) -> Session:
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.last_activity = datetime.now(UTC)
            return session
        session = Session(session_id=session_id, user_id=user_id, caller=caller)
        self._sessions[session_id] = session
        return session

    def append_message(self, *, session_id: str, message: dict[str, Any]) -> None:
        session = self._sessions[session_id]
        session.messages.append(message)
        session.last_activity = datetime.now(UTC)

    def update_caller(self, *, session_id: str, caller: CallerContext) -> None:
        session = self._sessions[session_id]
        session.caller = caller
        session.last_activity = datetime.now(UTC)
