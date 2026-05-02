"""Apply numbered .json mappings in lex order; track applied state in sidecar index."""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_STATE_INDEX = "lina_users_index_state"
_STATE_INDEX_BODY: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "applied_at": {"type": "date"},
            "filename": {"type": "keyword"},
        }
    },
}


@dataclass
class IndexRunner:
    client: Any
    mappings_dir: Path

    def apply_pending(self) -> list[str]:
        """Apply pending mappings in lex order. Return list of newly applied versions."""
        self._ensure_state_index()
        already = self._already_applied()
        applied: list[str] = []
        for path in sorted(self.mappings_dir.glob("*.json")):
            version = path.stem
            if version in already:
                continue
            self._apply_one(path)
            self.client.index(
                index=_STATE_INDEX,
                id=version,
                body={
                    "applied_at": _dt.datetime.now(_dt.UTC).isoformat(),
                    "filename": path.name,
                },
                refresh="wait_for",
            )
            applied.append(version)
        return applied

    def _ensure_state_index(self) -> None:
        if not self.client.indices.exists(index=_STATE_INDEX):
            self.client.indices.create(index=_STATE_INDEX, body=_STATE_INDEX_BODY)

    def _already_applied(self) -> set[str]:
        result = self.client.search(
            index=_STATE_INDEX,
            body={"size": 1000, "query": {"match_all": {}}, "_source": False},
        )
        return {hit["_id"] for hit in result["hits"]["hits"]}

    def _apply_one(self, path: Path) -> None:
        body = json.loads(path.read_text())
        # Index name is filename minus the leading numeric prefix and .json
        # e.g. "001_corp_user_profiles_v1" -> "corp_user_profiles_v1"
        index_name = path.stem.split("_", 1)[1]
        if not self.client.indices.exists(index=index_name):
            self.client.indices.create(index=index_name, body=body)
        else:
            mappings = body.get("mappings")
            if mappings:
                self.client.indices.put_mapping(index=index_name, body=mappings)


def list_pending(*, client: Any, mappings_dir: Path) -> list[str]:
    """Return the list of mapping versions that have not yet been applied."""
    if not client.indices.exists(index=_STATE_INDEX):
        return [p.stem for p in sorted(mappings_dir.glob("*.json"))]
    result = client.search(
        index=_STATE_INDEX,
        body={"size": 1000, "query": {"match_all": {}}, "_source": False},
    )
    already = {hit["_id"] for hit in result["hits"]["hits"]}
    return [p.stem for p in sorted(mappings_dir.glob("*.json")) if p.stem not in already]
