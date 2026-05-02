"""UserQueryTemplate ABC and OpenSearch DSL validator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, ClassVar

from pydantic import BaseModel

APPROVED_INDICES: frozenset[str] = frozenset({"corp_user_profiles_v1"})

ALLOWED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "query",
        "size",
        "from",
        "sort",
        "_source",
        "track_total_hits",
    }
)

FORBIDDEN_QUERY_CLAUSES: frozenset[str] = frozenset(
    {
        "script",
        "script_score",
        "script_query",
        "function_score",
        "runtime_mappings",
    }
)


class TemplateValidationError(RuntimeError):
    """Raised when a template's DSL body violates the spec §13 rules."""


def _walk_for_forbidden(node: Any) -> Iterable[str]:
    """Recursively yield any forbidden clause name found anywhere in the structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key in FORBIDDEN_QUERY_CLAUSES:
                yield key
            yield from _walk_for_forbidden(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_for_forbidden(item)


def validate_template_query(
    body: dict[str, Any],
    *,
    allowed_fields: frozenset[str],
    default_size: int,
    max_size: int,
) -> None:
    """Run the DSL sanity checks for spec §13 rules 1, 2, 6, 9, 13.

    Rules enforced here:
    - top-level keys allowlist (no aggs/script_fields)
    - no forbidden script-bearing clauses anywhere in the body
    - `_source` is `false` or a list ⊆ allowed_fields (no wildcards)
    - `sort` keys ⊆ allowed_fields
    - `size` ≤ max_size
    """
    if not isinstance(body, dict):
        raise TemplateValidationError(f"query body must be a dict, got {type(body).__name__}")

    for key in body:
        if key not in ALLOWED_TOP_LEVEL_KEYS:
            raise TemplateValidationError(f"top-level key {key!r} is not in ALLOWED_TOP_LEVEL_KEYS")

    forbidden = list(_walk_for_forbidden(body))
    if forbidden:
        raise TemplateValidationError(f"forbidden DSL clause(s) present: {sorted(set(forbidden))}")

    source = body.get("_source")
    if source is not None:
        if source is False:
            pass
        elif isinstance(source, list):
            for field in source:
                if not isinstance(field, str):
                    raise TemplateValidationError(
                        f"_source list entries must be strings; got {field!r}"
                    )
                if field == "*":
                    raise TemplateValidationError("_source must not contain wildcard '*'")
                if field not in allowed_fields:
                    raise TemplateValidationError(
                        f"_source field {field!r} is not in allowed_fields"
                    )
        else:
            raise TemplateValidationError(
                f"_source must be `false` or a list of field names; got {source!r}"
            )

    sort = body.get("sort")
    if sort is not None:
        if not isinstance(sort, list):
            raise TemplateValidationError(f"sort must be a list; got {sort!r}")
        for entry in sort:
            if isinstance(entry, str):
                field = entry
            elif isinstance(entry, dict) and len(entry) == 1:
                field = next(iter(entry))
            else:
                raise TemplateValidationError(
                    f"sort entry must be a str or single-key dict: {entry!r}"
                )
            if field not in allowed_fields:
                raise TemplateValidationError(f"sort field {field!r} is not in allowed_fields")

    size = body.get("size")
    if size is not None:
        if not isinstance(size, int) or isinstance(size, bool):
            raise TemplateValidationError(f"size must be an int; got {size!r}")
        if size > max_size:
            raise TemplateValidationError(f"size {size} exceeds max_size {max_size}")
        if size < 0:
            raise TemplateValidationError(f"size must be non-negative; got {size}")

    _ = default_size  # currently advisory only; worker injects when missing


class UserQueryTemplate(ABC):
    query_type: ClassVar[str]
    allowed_roles: ClassVar[frozenset[str]]
    Params: ClassVar[type[BaseModel]]
    default_size: ClassVar[int]
    max_size: ClassVar[int]
    template_version: ClassVar[str]
    index: ClassVar[str]
    allowed_fields: ClassVar[frozenset[str]]

    @abstractmethod
    def build_query(self, params: BaseModel) -> dict[str, Any]:
        """Return the OpenSearch search body (dict)."""

    @abstractmethod
    def shape_packet(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Project hit `_source` rows to allowlisted fields."""

    def validate_at_import(self) -> None:
        """Run DSL sanity check against a representative body produced by build_query."""
        if self.index not in APPROVED_INDICES:
            raise TemplateValidationError(f"template index {self.index!r} not in APPROVED_INDICES")
        params = self.Params.model_construct()
        body = self.build_query(params)
        validate_template_query(
            body,
            allowed_fields=self.allowed_fields,
            default_size=self.default_size,
            max_size=self.max_size,
        )
