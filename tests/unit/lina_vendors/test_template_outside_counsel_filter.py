"""Unit tests for outside_counsel_filter template."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lina_vendors.templates.outside_counsel_filter import (
    OutsideCounselFilterParams,
    OutsideCounselFilterTemplate,
)


@pytest.mark.unit
def test_outside_counsel_filter_no_filters_uses_match_all() -> None:
    tmpl = OutsideCounselFilterTemplate()
    body = tmpl.build_query(OutsideCounselFilterParams())
    assert body["query"]["bool"]["must"] == [{"match_all": {}}]


@pytest.mark.unit
def test_outside_counsel_filter_combines_must_clauses() -> None:
    tmpl = OutsideCounselFilterTemplate()
    body = tmpl.build_query(
        OutsideCounselFilterParams(
            vendor_id=["vendor_walker"],
            timekeeper_classification=["Partner", "Associate"],
        )
    )
    must = body["query"]["bool"]["must"]
    assert {"terms": {"vendor_id": ["vendor_walker"]}} in must
    assert {"terms": {"timekeeper_classification": ["Partner", "Associate"]}} in must


@pytest.mark.unit
def test_outside_counsel_filter_rate_range_requires_currency() -> None:
    with pytest.raises(ValidationError, match="currency_code"):
        OutsideCounselFilterParams(min_effective_hourly_rate=500.0)
    with pytest.raises(ValidationError, match="currency_code"):
        OutsideCounselFilterParams(max_effective_hourly_rate=1000.0)


@pytest.mark.unit
def test_outside_counsel_filter_rate_range_with_currency_emits_filter() -> None:
    tmpl = OutsideCounselFilterTemplate()
    body = tmpl.build_query(
        OutsideCounselFilterParams(
            min_effective_hourly_rate=500.0,
            max_effective_hourly_rate=1000.0,
            currency_code="USD",
        )
    )
    filters = body["query"]["bool"]["filter"]
    assert {"range": {"effective_hourly_rate": {"gte": 500.0, "lte": 1000.0}}} in filters
    assert {"term": {"currency_code": "USD"}} in filters


@pytest.mark.unit
def test_outside_counsel_filter_role_restrictions() -> None:
    tmpl = OutsideCounselFilterTemplate()
    assert tmpl.allowed_roles == frozenset({"legal_ops", "finance", "procurement"})
