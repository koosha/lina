"""Unit tests for people_filter template."""

from __future__ import annotations

import pytest

from lina_users.templates.people_filter import PeopleFilterParams, PeopleFilterTemplate


@pytest.mark.unit
def test_people_filter_no_filters_uses_match_all() -> None:
    tmpl = PeopleFilterTemplate()
    body = tmpl.build_query(PeopleFilterParams())
    assert body["query"]["bool"]["must"] == [{"match_all": {}}]


@pytest.mark.unit
def test_people_filter_combines_multiple_terms_clauses() -> None:
    tmpl = PeopleFilterTemplate()
    body = tmpl.build_query(
        PeopleFilterParams(
            department=["Legal"],
            roles=["legal_ops"],
            permission_tags=["matter_owner"],
            user_status=["active"],
        )
    )
    must = body["query"]["bool"]["must"]
    assert {"terms": {"department": ["Legal"]}} in must
    assert {"terms": {"roles": ["legal_ops"]}} in must
    assert {"terms": {"permission_tags": ["matter_owner"]}} in must
    assert {"terms": {"user_status": ["active"]}} in must


@pytest.mark.unit
def test_people_filter_size_clamps() -> None:
    tmpl = PeopleFilterTemplate()
    body = tmpl.build_query(PeopleFilterParams(size=10_000))
    assert body["size"] == tmpl.max_size


@pytest.mark.unit
def test_people_filter_default_size_when_unset() -> None:
    tmpl = PeopleFilterTemplate()
    body = tmpl.build_query(PeopleFilterParams())
    assert body["size"] == tmpl.default_size


@pytest.mark.unit
def test_people_filter_shape_packet_filters_unknown() -> None:
    tmpl = PeopleFilterTemplate()
    shaped = tmpl.shape_packet(
        [
            {"_source": {"user_id": "u1", "department": "Legal", "ssn": "xxx"}},
        ]
    )
    assert shaped == [{"user_id": "u1", "department": "Legal"}]


@pytest.mark.unit
def test_people_filter_open_to_any_role() -> None:
    tmpl = PeopleFilterTemplate()
    assert tmpl.allowed_roles == frozenset({"*"})
