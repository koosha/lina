"""Unit tests for lawyer_search template."""

from __future__ import annotations

import pytest

from lina_vendors.templates.lawyer_search import LawyerSearchParams, LawyerSearchTemplate


@pytest.mark.unit
def test_lawyer_search_with_query_uses_multi_match() -> None:
    tmpl = LawyerSearchTemplate()
    body = tmpl.build_query(LawyerSearchParams(query="patricia walker"))
    must = body["query"]["bool"]["must"]
    assert len(must) == 1
    assert "multi_match" in must[0]
    fields = must[0]["multi_match"]["fields"]
    assert "display_name^2" in fields
    assert "first_name" in fields
    assert "last_name" in fields
    assert "vendor_name" in fields
    assert "expertise_summary" in fields


@pytest.mark.unit
def test_lawyer_search_empty_query_uses_match_all() -> None:
    tmpl = LawyerSearchTemplate()
    body = tmpl.build_query(LawyerSearchParams())
    assert body["query"]["bool"]["must"] == [{"match_all": {}}]


@pytest.mark.unit
def test_lawyer_search_filters_become_terms_clauses() -> None:
    tmpl = LawyerSearchTemplate()
    body = tmpl.build_query(
        LawyerSearchParams(
            query="privacy",
            practice_areas=["Privacy", "Compliance"],
            jurisdictions=["US", "GB"],
            bar_admissions=["NY", "CA"],
        )
    )
    filters = body["query"]["bool"]["filter"]
    assert {"terms": {"practice_areas": ["Privacy", "Compliance"]}} in filters
    assert {"terms": {"jurisdictions": ["US", "GB"]}} in filters
    assert {"terms": {"bar_admissions": ["NY", "CA"]}} in filters


@pytest.mark.unit
def test_lawyer_search_size_clamps_to_max() -> None:
    tmpl = LawyerSearchTemplate()
    body = tmpl.build_query(LawyerSearchParams(query="x", size=10_000))
    assert body["size"] == tmpl.max_size


@pytest.mark.unit
def test_lawyer_search_shape_packet_filters_unknown_fields() -> None:
    tmpl = LawyerSearchTemplate()
    shaped = tmpl.shape_packet(
        [{"_source": {"timekeeper_id": "tk1", "internal_blob": "x", "vendor_name": "Walker"}}]
    )
    assert shaped == [{"timekeeper_id": "tk1", "vendor_name": "Walker"}]
