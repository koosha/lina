"""Unit tests for user_search template."""

from __future__ import annotations

import pytest

from lina_users.templates.user_search import UserSearchParams, UserSearchTemplate


@pytest.mark.unit
def test_user_search_with_query_uses_multi_match() -> None:
    tmpl = UserSearchTemplate()
    body = tmpl.build_query(UserSearchParams(query="jane smith"))
    must = body["query"]["bool"]["must"]
    assert len(must) == 1
    assert "multi_match" in must[0]
    fields = must[0]["multi_match"]["fields"]
    assert "display_name^2" in fields
    assert "first_name" in fields
    assert "last_name" in fields
    assert "job_title" in fields
    assert "email_text" in fields


@pytest.mark.unit
def test_user_search_empty_query_uses_match_all() -> None:
    tmpl = UserSearchTemplate()
    body = tmpl.build_query(UserSearchParams())
    assert body["query"]["bool"]["must"] == [{"match_all": {}}]


@pytest.mark.unit
def test_user_search_filters_become_terms_clauses() -> None:
    tmpl = UserSearchTemplate()
    body = tmpl.build_query(
        UserSearchParams(
            query="counsel",
            department=["Legal"],
            business_unit=["Enterprise", "Product"],
            region=["AMER"],
            user_status=["active"],
        )
    )
    filters = body["query"]["bool"]["filter"]
    assert {"terms": {"department": ["Legal"]}} in filters
    assert {"terms": {"business_unit": ["Enterprise", "Product"]}} in filters
    assert {"terms": {"region": ["AMER"]}} in filters
    assert {"terms": {"user_status": ["active"]}} in filters


@pytest.mark.unit
def test_user_search_size_defaults_and_clamps() -> None:
    tmpl = UserSearchTemplate()
    default_body = tmpl.build_query(UserSearchParams(query="x"))
    assert default_body["size"] == tmpl.default_size
    clamped = tmpl.build_query(UserSearchParams(query="x", size=10_000))
    assert clamped["size"] == tmpl.max_size


@pytest.mark.unit
def test_user_search_shape_packet_filters_fields() -> None:
    tmpl = UserSearchTemplate()
    shaped = tmpl.shape_packet(
        [{"_source": {"user_id": "u1", "internal_secret": "x", "department": "Legal"}}]
    )
    assert shaped == [{"user_id": "u1", "department": "Legal"}]
