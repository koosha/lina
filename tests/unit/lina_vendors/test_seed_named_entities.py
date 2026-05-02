"""Unit tests for the hand-written named timekeepers."""

from __future__ import annotations

import pytest

from lina_vendors.seed.named_entities import NAMED_TIMEKEEPERS, named_timekeeper_docs


@pytest.mark.unit
def test_named_timekeepers_count_is_five() -> None:
    assert len(NAMED_TIMEKEEPERS) == 5


@pytest.mark.unit
def test_named_timekeepers_required_ids() -> None:
    """These IDs must exist for cross-subsystem ID parity with `lina_redshift`."""
    ids = {t.timekeeper_id for t in NAMED_TIMEKEEPERS}
    expected = {
        "tk_walker_partner",
        "tk_walker_associate",
        "tk_jones_partner",
        "tk_meridian_partner",
        "tk_meridian_paralegal",
    }
    assert ids == expected


@pytest.mark.unit
def test_named_timekeepers_have_unique_ids() -> None:
    ids = [t.timekeeper_id for t in NAMED_TIMEKEEPERS]
    assert len(set(ids)) == len(ids)


@pytest.mark.unit
def test_named_timekeeper_docs_carry_required_opensearch_fields() -> None:
    docs = named_timekeeper_docs()
    for doc in docs:
        assert doc["practice_areas"]  # non-empty list
        assert doc["jurisdictions"]
        assert doc["currency_code"] in {"USD", "GBP", "EUR"}
        assert "expertise_summary" in doc
        assert "representative_matters_summary" in doc
        assert doc["effective_hourly_rate"] > 0


@pytest.mark.unit
def test_walker_partner_rate_matches_redshift_named_rate() -> None:
    """Patricia Walker's standard hourly rate must equal C's NAMED_RATES entry (USD 950)."""
    walker = next(t for t in NAMED_TIMEKEEPERS if t.timekeeper_id == "tk_walker_partner")
    assert walker.standard_hourly_rate == 950.0
    assert walker.currency_code == "USD"
