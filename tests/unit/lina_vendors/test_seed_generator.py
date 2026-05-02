"""Unit tests for the deterministic Faker bulk generator."""

from __future__ import annotations

import pytest

from lina_vendors.seed.generator import generate_timekeepers
from lina_vendors.seed.named_entities import NAMED_TIMEKEEPERS


@pytest.mark.unit
def test_generate_timekeepers_returns_requested_count() -> None:
    docs = generate_timekeepers(count=200, seed=42)
    assert len(docs) == 200


@pytest.mark.unit
def test_generate_timekeepers_is_deterministic() -> None:
    a = generate_timekeepers(count=200, seed=42)
    b = generate_timekeepers(count=200, seed=42)
    assert a == b


@pytest.mark.unit
def test_generated_timekeeper_ids_are_zero_padded() -> None:
    docs = generate_timekeepers(count=200, seed=42)
    ids = [d["timekeeper_id"] for d in docs]
    assert ids[0] == "tk_b_gen_000"
    assert ids[-1] == "tk_b_gen_199"
    for tid in ids:
        assert isinstance(tid, str)
        assert tid.startswith("tk_b_gen_")


@pytest.mark.unit
def test_generated_ids_are_unique() -> None:
    docs = generate_timekeepers(count=200, seed=42)
    ids = [d["timekeeper_id"] for d in docs]
    assert len(set(ids)) == len(ids)


@pytest.mark.unit
def test_generated_ids_disjoint_from_named() -> None:
    docs = generate_timekeepers(count=200, seed=42)
    generated_ids = {d["timekeeper_id"] for d in docs}
    named_ids = {t.timekeeper_id for t in NAMED_TIMEKEEPERS}
    assert generated_ids.isdisjoint(named_ids)


@pytest.mark.unit
def test_generated_vendor_ids_are_b_namespaced_and_disjoint_from_c() -> None:
    """Vendor IDs must be `vendor_b_gen_*` — disjoint from Subsystem C's vendor namespace."""
    docs = generate_timekeepers(count=200, seed=42)
    vendor_ids = {d["vendor_id"] for d in docs}
    assert vendor_ids == {f"vendor_b_gen_{v:03d}" for v in range(10)}
    # Disjoint from named B vendors
    named_vendor_ids = {t.vendor_id for t in NAMED_TIMEKEEPERS}
    assert vendor_ids.isdisjoint(named_vendor_ids)
