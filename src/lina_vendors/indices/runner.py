"""Subsystem B index runner — thin wrapper that binds the core runner to the B state index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lina_core.opensearch import IndexRunner as _CoreIndexRunner
from lina_core.opensearch import list_pending as _core_list_pending

_STATE_INDEX = "lina_vendors_index_state"


@dataclass
class IndexRunner:
    """Subsystem-B flavored runner — fixes `state_index` to `lina_vendors_index_state`."""

    client: Any
    mappings_dir: Path

    def apply_pending(self) -> list[str]:
        return _CoreIndexRunner(
            client=self.client,
            mappings_dir=self.mappings_dir,
            state_index=_STATE_INDEX,
        ).apply_pending()


def list_pending(*, client: Any, mappings_dir: Path) -> list[str]:
    """Return the list of mapping versions that have not yet been applied."""
    return _core_list_pending(
        client=client,
        mappings_dir=mappings_dir,
        state_index=_STATE_INDEX,
    )
