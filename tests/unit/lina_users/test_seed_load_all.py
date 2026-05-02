"""Cross-subsystem parity + load_all integration with the OpenSearch container."""

from __future__ import annotations

from typing import Any

import pytest

from lina_users.seed import load_all


@pytest.mark.unit
def test_named_users_match_redshift_matter_owners() -> None:
    """Cross-subsystem ID contract: every matter_owner_user_id from C must exist in A."""
    from lina_redshift.seed.named_entities import NAMED_MATTERS
    from lina_users.seed.named_entities import NAMED_USERS

    owner_ids = {m.matter_owner_user_id for m in NAMED_MATTERS}
    named_user_ids = {u.user_id for u in NAMED_USERS}
    assert owner_ids <= named_user_ids


@pytest.mark.unit
def test_load_all_inserts_named_and_generated(opensearch_client: Any) -> None:
    """Container-backed: load_all writes 60 docs into the index."""
    if opensearch_client.indices.exists(index="corp_user_profiles_v1"):
        opensearch_client.indices.delete(index="corp_user_profiles_v1")
    if opensearch_client.indices.exists(index="lina_users_index_state"):
        opensearch_client.indices.delete(index="lina_users_index_state")

    counts = load_all(opensearch_client, reset=False)
    assert counts == {"named": 10, "generated": 50, "total": 60}

    opensearch_client.indices.refresh(index="corp_user_profiles_v1")
    result = opensearch_client.count(index="corp_user_profiles_v1")
    assert result["count"] == 60


@pytest.mark.unit
def test_load_all_reset_recreates_index(opensearch_client: Any) -> None:
    """When reset=True, the existing index is wiped before re-applying the mapping."""
    load_all(opensearch_client, reset=True)
    opensearch_client.indices.refresh(index="corp_user_profiles_v1")
    first = opensearch_client.count(index="corp_user_profiles_v1")["count"]
    # Re-running with reset=True should leave us at the same total
    load_all(opensearch_client, reset=True)
    opensearch_client.indices.refresh(index="corp_user_profiles_v1")
    second = opensearch_client.count(index="corp_user_profiles_v1")["count"]
    assert first == second == 60
