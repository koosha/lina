"""Unit tests for user_lookup template."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lina_users.templates.user_lookup import UserLookupParams, UserLookupTemplate


@pytest.mark.unit
def test_user_lookup_requires_exactly_one_id() -> None:
    with pytest.raises(ValidationError):
        UserLookupParams()
    with pytest.raises(ValidationError):
        UserLookupParams(user_id="u1", email="a@b.com")


@pytest.mark.unit
def test_user_lookup_by_user_id_builds_term_query() -> None:
    tmpl = UserLookupTemplate()
    params = UserLookupParams(user_id="user_jane_smith")
    body = tmpl.build_query(params)
    assert body["query"]["bool"]["must"] == [{"term": {"user_id": "user_jane_smith"}}]


@pytest.mark.unit
def test_user_lookup_by_email_builds_term_query() -> None:
    tmpl = UserLookupTemplate()
    params = UserLookupParams(email="jane@acme.com")
    body = tmpl.build_query(params)
    assert body["query"]["bool"]["must"] == [{"term": {"email": "jane@acme.com"}}]


@pytest.mark.unit
def test_user_lookup_active_filter_present_by_default() -> None:
    tmpl = UserLookupTemplate()
    body = tmpl.build_query(UserLookupParams(user_id="u1"))
    assert {"term": {"user_status": "active"}} in body["query"]["bool"]["filter"]


@pytest.mark.unit
def test_user_lookup_include_inactive_drops_filter() -> None:
    tmpl = UserLookupTemplate()
    body = tmpl.build_query(UserLookupParams(user_id="u1", include_inactive=True))
    assert body["query"]["bool"]["filter"] == []


@pytest.mark.unit
def test_user_lookup_size_clamps_to_max() -> None:
    tmpl = UserLookupTemplate()
    body = tmpl.build_query(UserLookupParams(user_id="u1", size=99999))
    assert body["size"] == tmpl.max_size


@pytest.mark.unit
def test_user_lookup_shape_packet_drops_unknown_fields() -> None:
    tmpl = UserLookupTemplate()
    hits = [
        {"_source": {"user_id": "u1", "secret_blob": "xxx", "display_name": "Jane"}},
    ]
    shaped = tmpl.shape_packet(hits)
    assert shaped == [{"user_id": "u1", "display_name": "Jane"}]


@pytest.mark.unit
def test_user_lookup_template_metadata() -> None:
    tmpl = UserLookupTemplate()
    assert tmpl.allowed_roles == frozenset({"*"})
    assert tmpl.index == "corp_user_profiles_v1"
