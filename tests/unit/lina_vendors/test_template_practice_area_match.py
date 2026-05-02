"""Unit tests for practice_area_match template."""

from __future__ import annotations

import pytest

from lina_vendors.templates.practice_area_match import (
    PracticeAreaMatchParams,
    PracticeAreaMatchTemplate,
)


@pytest.mark.unit
def test_practice_area_match_with_query_uses_match_clause() -> None:
    tmpl = PracticeAreaMatchTemplate()
    body = tmpl.build_query(
        PracticeAreaMatchParams(expertise_query="data privacy GDPR enforcement")
    )
    must = body["query"]["bool"]["must"]
    assert must == [{"match": {"expertise_summary": "data privacy GDPR enforcement"}}]


@pytest.mark.unit
def test_practice_area_match_empty_uses_match_all() -> None:
    tmpl = PracticeAreaMatchTemplate()
    body = tmpl.build_query(PracticeAreaMatchParams())
    assert body["query"]["bool"]["must"] == [{"match_all": {}}]


@pytest.mark.unit
def test_practice_area_match_filters_emit_terms() -> None:
    tmpl = PracticeAreaMatchTemplate()
    body = tmpl.build_query(
        PracticeAreaMatchParams(
            expertise_query="biotech IP",
            practice_areas=["IP", "Patents"],
            jurisdictions=["US"],
            industries=["Biotech"],
        )
    )
    filters = body["query"]["bool"]["filter"]
    assert {"terms": {"practice_areas": ["IP", "Patents"]}} in filters
    assert {"terms": {"jurisdictions": ["US"]}} in filters
    assert {"terms": {"industries": ["Biotech"]}} in filters


@pytest.mark.unit
def test_practice_area_match_size_defaults_and_clamps() -> None:
    tmpl = PracticeAreaMatchTemplate()
    default_body = tmpl.build_query(PracticeAreaMatchParams(expertise_query="x"))
    assert default_body["size"] == tmpl.default_size
    clamped = tmpl.build_query(PracticeAreaMatchParams(expertise_query="x", size=10_000))
    assert clamped["size"] == tmpl.max_size


@pytest.mark.unit
def test_practice_area_match_open_to_any_role() -> None:
    tmpl = PracticeAreaMatchTemplate()
    assert tmpl.allowed_roles == frozenset({"*"})
