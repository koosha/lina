"""Unit tests for Session + InMemorySessionStore."""

from __future__ import annotations

import pytest

from lina_core.caller import CallerContext
from lina_supervisor.session import InMemorySessionStore, Session, SessionStore


def _caller(*, user_id: str = "user_jane", request_id: str = "req-1") -> CallerContext:
    return CallerContext(
        user_id=user_id,
        roles=frozenset({"reader"}),
        request_id=request_id,
    )


@pytest.mark.unit
def test_session_creation_with_caller() -> None:
    caller = _caller()
    session = Session(session_id="s1", user_id="user_jane", caller=caller)
    assert session.session_id == "s1"
    assert session.user_id == "user_jane"
    assert session.caller == caller
    assert session.messages == []
    assert session.worker_call_count_total == 0


@pytest.mark.unit
def test_get_or_create_returns_existing_session() -> None:
    store = InMemorySessionStore()
    caller = _caller()
    a = store.get_or_create(session_id="s1", user_id="user_jane", caller=caller)
    a.worker_call_count_total = 5
    b = store.get_or_create(session_id="s1", user_id="user_jane", caller=caller)
    assert b is a
    assert b.worker_call_count_total == 5


@pytest.mark.unit
def test_get_or_create_initializes_new_session() -> None:
    store = InMemorySessionStore()
    caller = _caller()
    session = store.get_or_create(session_id="s1", user_id="user_jane", caller=caller)
    assert session.session_id == "s1"
    assert session.messages == []


@pytest.mark.unit
def test_append_message_grows_list() -> None:
    store = InMemorySessionStore()
    caller = _caller()
    store.get_or_create(session_id="s1", user_id="user_jane", caller=caller)
    store.append_message(session_id="s1", message={"role": "user", "content": "hi"})
    store.append_message(session_id="s1", message={"role": "assistant", "content": "hello"})
    session = store.get_or_create(session_id="s1", user_id="user_jane", caller=caller)
    assert len(session.messages) == 2
    assert session.messages[0]["content"] == "hi"


@pytest.mark.unit
def test_update_caller_replaces_caller() -> None:
    store = InMemorySessionStore()
    original = _caller(user_id="user_jane", request_id="req-1")
    store.get_or_create(session_id="s1", user_id="user_jane", caller=original)
    refreshed = _caller(user_id="user_jane", request_id="req-2")
    store.update_caller(session_id="s1", caller=refreshed)
    session = store.get_or_create(session_id="s1", user_id="user_jane", caller=original)
    assert session.caller.request_id == "req-2"


@pytest.mark.unit
def test_protocol_compliance() -> None:
    """InMemorySessionStore must satisfy the SessionStore Protocol."""
    store: SessionStore = InMemorySessionStore()
    assert hasattr(store, "get_or_create")
    assert hasattr(store, "append_message")
    assert hasattr(store, "update_caller")
