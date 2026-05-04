"""Seed loaders for `vendor_lawyer_profiles_v1`.

`load_all` performs a bulk insert of named + generated timekeepers via the
OpenSearch bulk API. `_id` is set to `timekeeper_id` for idempotency.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lina_vendors.indices.runner import IndexRunner
from lina_vendors.seed.generator import generate_timekeepers
from lina_vendors.seed.named_entities import named_timekeeper_docs

_INDEX = "vendor_lawyer_profiles_v1"
_STATE_INDEX = "lina_vendors_index_state"


def _bulk_actions(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build helpers.bulk action dicts."""
    return [
        {
            "_index": _INDEX,
            "_id": doc["timekeeper_id"],
            "_source": doc,
        }
        for doc in docs
    ]


def _mappings_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "indices" / "mappings"


def load_all(client: Any, *, reset: bool = False) -> dict[str, int]:
    """Bulk-load named + generated timekeepers.

    When `reset=True`, deletes the existing index first and reapplies the mapping.
    Returns counts: {"named": N, "generated": M, "total": N+M}.
    """
    from opensearchpy import helpers

    if reset:
        if client.indices.exists(index=_INDEX):
            client.indices.delete(index=_INDEX)
        # See lina_users.seed.load_all — also reset the migration ledger
        # so apply_pending re-creates the data index with the explicit
        # mapping instead of letting dynamic mapping kick in on first
        # bulk insert.
        if client.indices.exists(index=_STATE_INDEX):
            client.indices.delete(index=_STATE_INDEX)

    runner = IndexRunner(client=client, mappings_dir=_mappings_dir())
    runner.apply_pending()

    named = named_timekeeper_docs()
    generated = generate_timekeepers(count=200, seed=42)

    actions = _bulk_actions(named) + _bulk_actions(generated)
    helpers.bulk(client, actions, refresh="wait_for")
    # See lina_users.seed: `wait_for` isn't enough on managed OpenSearch.
    client.indices.refresh(index=_INDEX)

    return {
        "named": len(named),
        "generated": len(generated),
        "total": len(named) + len(generated),
    }
