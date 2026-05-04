"""Seed loaders for `corp_user_profiles_v1`.

`load_all` performs a bulk insert of named + generated users via the OpenSearch
bulk API. `_id` is set to `user_id` for idempotency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lina_users.indices.runner import IndexRunner
from lina_users.seed.generator import generate_users
from lina_users.seed.named_entities import named_user_docs

_INDEX = "corp_user_profiles_v1"


def _bulk_actions(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build helpers.bulk action dicts."""
    return [
        {
            "_index": _INDEX,
            "_id": doc["user_id"],
            "_source": doc,
        }
        for doc in docs
    ]


def _mappings_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "indices" / "mappings"


def load_all(client: Any, *, reset: bool = False) -> dict[str, int]:
    """Bulk-load named + generated users.

    When `reset=True`, deletes the existing index first and reapplies the mapping.
    Returns counts: {"named": N, "generated": M, "total": N+M}.
    """
    from opensearchpy import helpers

    if reset and client.indices.exists(index=_INDEX):
        client.indices.delete(index=_INDEX)

    runner = IndexRunner(client=client, mappings_dir=_mappings_dir())
    runner.apply_pending()

    named = named_user_docs()
    generated = generate_users(count=50, seed=42)

    actions = _bulk_actions(named) + _bulk_actions(generated)
    helpers.bulk(client, actions, refresh="wait_for")
    # `wait_for` should make the docs searchable, but on managed OpenSearch
    # domains we've seen the next-bulk-search return 0 hits if the new
    # documents haven't been refreshed yet. Force a refresh so any caller —
    # CI, an operator, or a follow-up integration test — observes a
    # consistent, queryable index immediately.
    client.indices.refresh(index=_INDEX)

    return {
        "named": len(named),
        "generated": len(generated),
        "total": len(named) + len(generated),
    }
