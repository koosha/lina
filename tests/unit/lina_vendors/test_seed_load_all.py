"""Cross-subsystem parity + load_all integration with the OpenSearch container."""

from __future__ import annotations

from typing import Any

import pytest

from lina_vendors.seed import load_all


@pytest.mark.unit
def test_named_timekeepers_match_redshift_dim_timekeeper() -> None:
    """Cross-subsystem ID contract: B and C must share the same named-timekeeper IDs."""
    from lina_redshift.seed.named_entities import NAMED_TIMEKEEPERS as C_TK
    from lina_vendors.seed.named_entities import NAMED_TIMEKEEPERS as B_TK

    b_ids = {t.timekeeper_id for t in B_TK}
    c_ids = {t.timekeeper_id for t in C_TK}
    assert b_ids == c_ids


@pytest.mark.unit
def test_load_all_inserts_named_and_generated(opensearch_client: Any) -> None:
    """Container-backed: load_all writes 205 docs into the index."""
    if opensearch_client.indices.exists(index="vendor_lawyer_profiles_v1"):
        opensearch_client.indices.delete(index="vendor_lawyer_profiles_v1")
    if opensearch_client.indices.exists(index="lina_vendors_index_state"):
        opensearch_client.indices.delete(index="lina_vendors_index_state")

    counts = load_all(opensearch_client, reset=False)
    assert counts == {"named": 5, "generated": 200, "total": 205}

    opensearch_client.indices.refresh(index="vendor_lawyer_profiles_v1")
    result = opensearch_client.count(index="vendor_lawyer_profiles_v1")
    assert result["count"] == 205


@pytest.mark.unit
def test_load_all_reset_recreates_index(opensearch_client: Any) -> None:
    """When reset=True, the existing index is wiped before re-applying the mapping."""
    load_all(opensearch_client, reset=True)
    opensearch_client.indices.refresh(index="vendor_lawyer_profiles_v1")
    first = opensearch_client.count(index="vendor_lawyer_profiles_v1")["count"]
    load_all(opensearch_client, reset=True)
    opensearch_client.indices.refresh(index="vendor_lawyer_profiles_v1")
    second = opensearch_client.count(index="vendor_lawyer_profiles_v1")["count"]
    assert first == second == 205
