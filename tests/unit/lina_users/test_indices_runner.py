"""Unit tests for the lina_users index runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lina_users.indices.runner import IndexRunner

MAPPINGS_DIR = Path(__file__).resolve().parents[3] / "src" / "lina_users" / "indices" / "mappings"


@pytest.fixture
def runner(opensearch_client: Any) -> IndexRunner:
    # Ensure clean slate between tests
    if opensearch_client.indices.exists(index="corp_user_profiles_v1"):
        opensearch_client.indices.delete(index="corp_user_profiles_v1")
    if opensearch_client.indices.exists(index="lina_users_index_state"):
        opensearch_client.indices.delete(index="lina_users_index_state")
    return IndexRunner(client=opensearch_client, mappings_dir=MAPPINGS_DIR)


@pytest.mark.unit
def test_apply_pending_creates_index(runner: IndexRunner, opensearch_client: Any) -> None:
    runner.apply_pending()
    assert opensearch_client.indices.exists(index="corp_user_profiles_v1")


@pytest.mark.unit
def test_apply_pending_records_state(runner: IndexRunner, opensearch_client: Any) -> None:
    runner.apply_pending()
    opensearch_client.indices.refresh(index="lina_users_index_state")
    state = opensearch_client.search(
        index="lina_users_index_state",
        body={"query": {"match_all": {}}},
    )
    versions = {hit["_id"] for hit in state["hits"]["hits"]}
    assert "001_corp_user_profiles_v1" in versions


@pytest.mark.unit
def test_apply_pending_idempotent(runner: IndexRunner, opensearch_client: Any) -> None:
    first = runner.apply_pending()
    assert first  # at least one version applied
    second = runner.apply_pending()
    assert second == []  # nothing newly applied
