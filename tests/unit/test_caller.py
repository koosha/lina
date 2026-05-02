"""Unit tests for CallerContext."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lina_redshift.caller import CallerContext


@pytest.mark.unit
def test_valid_caller() -> None:
    c = CallerContext(
        user_id="user_jane",
        roles=frozenset({"legal_ops"}),
        request_id="req_1",
    )
    assert c.user_id == "user_jane"
    assert "legal_ops" in c.roles
    assert c.permission_tags == frozenset()


@pytest.mark.unit
def test_caller_rejects_empty_user_id() -> None:
    with pytest.raises(ValidationError):
        CallerContext(user_id="", roles=frozenset({"legal_ops"}), request_id="req_1")


@pytest.mark.unit
def test_caller_rejects_empty_roles() -> None:
    with pytest.raises(ValidationError):
        CallerContext(user_id="user_jane", roles=frozenset(), request_id="req_1")


@pytest.mark.unit
def test_caller_role_intersection() -> None:
    c = CallerContext(
        user_id="user_jane",
        roles=frozenset({"legal_ops", "finance"}),
        request_id="req_1",
    )
    assert c.has_any_role(frozenset({"legal_ops"}))
    assert c.has_any_role(frozenset({"finance", "rate_admin"}))
    assert not c.has_any_role(frozenset({"rate_admin"}))


@pytest.mark.unit
def test_caller_wildcard_template_admits_any_role() -> None:
    """Templates with allowed_roles == {'*'} accept any non-empty role set."""
    c = CallerContext(
        user_id="user_jane",
        roles=frozenset({"some_arbitrary_role"}),
        request_id="req_1",
    )
    assert c.has_any_role(frozenset({"*"}))
