"""Unit tests for the deterministic Faker bulk generator."""

from __future__ import annotations

import pytest

from lina_users.seed.generator import generate_users
from lina_users.seed.named_entities import NAMED_USERS


@pytest.mark.unit
def test_generate_users_returns_requested_count() -> None:
    docs = generate_users(count=50, seed=42)
    assert len(docs) == 50


@pytest.mark.unit
def test_generate_users_is_deterministic() -> None:
    a = generate_users(count=50, seed=42)
    b = generate_users(count=50, seed=42)
    assert a == b


@pytest.mark.unit
def test_generated_user_ids_are_zero_padded() -> None:
    docs = generate_users(count=50, seed=42)
    ids = [d["user_id"] for d in docs]
    assert ids[0] == "user_gen_000"
    assert ids[-1] == "user_gen_049"
    # All IDs match the prefix pattern
    for uid in ids:
        assert isinstance(uid, str)
        assert uid.startswith("user_gen_")


@pytest.mark.unit
def test_generated_ids_are_unique() -> None:
    docs = generate_users(count=50, seed=42)
    ids = [d["user_id"] for d in docs]
    assert len(set(ids)) == len(ids)


@pytest.mark.unit
def test_generated_ids_disjoint_from_named() -> None:
    docs = generate_users(count=50, seed=42)
    generated_ids = {d["user_id"] for d in docs}
    named_ids = {u.user_id for u in NAMED_USERS}
    assert generated_ids.isdisjoint(named_ids)


@pytest.mark.unit
def test_generated_users_distributed_across_regions() -> None:
    """At a count of 50, all three regions should be represented."""
    docs = generate_users(count=50, seed=42)
    regions = {d["region"] for d in docs}
    assert regions == {"AMER", "EMEA", "APAC"}
