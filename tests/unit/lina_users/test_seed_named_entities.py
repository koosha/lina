"""Unit tests for the hand-written named users."""

from __future__ import annotations

import pytest

from lina_users.seed.named_entities import NAMED_USERS, named_user_docs


@pytest.mark.unit
def test_named_users_count_is_ten() -> None:
    assert len(NAMED_USERS) == 10


@pytest.mark.unit
def test_named_users_contain_required_ids() -> None:
    """These IDs must exist for cross-subsystem ID parity with `lina_redshift`."""
    ids = {u.user_id for u in NAMED_USERS}
    for required in (
        "user_jane_smith",
        "user_alex_lee",
        "user_sam_rodriguez",
        "user_taylor_kim",
        "user_pat_brown",
        "user_jordan_chen",
    ):
        assert required in ids


@pytest.mark.unit
def test_named_users_have_unique_ids() -> None:
    ids = [u.user_id for u in NAMED_USERS]
    assert len(set(ids)) == len(ids)


@pytest.mark.unit
def test_named_user_docs_contain_email_text_mirror() -> None:
    docs = named_user_docs()
    for doc in docs:
        assert doc["email_text"] == doc["email"]


@pytest.mark.unit
def test_named_users_manager_links_resolve_internally() -> None:
    """Every non-null manager_user_id must point at another named user."""
    ids = {u.user_id for u in NAMED_USERS}
    for u in NAMED_USERS:
        if u.manager_user_id is not None:
            assert u.manager_user_id in ids
