"""VendorQueryTemplate ABC. The DSL validator is shared via lina_users.templates.base."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

# Re-use the DSL validator from Subsystem A — both subsystems share the same
# OpenSearch DSL safety rules, only the approved index list differs.
from lina_users.templates.base import (
    ALLOWED_TOP_LEVEL_KEYS,
    FORBIDDEN_QUERY_CLAUSES,
    TemplateValidationError,
    validate_template_query,
)

APPROVED_INDICES: frozenset[str] = frozenset({"vendor_lawyer_profiles_v1"})

__all__ = [
    "ALLOWED_TOP_LEVEL_KEYS",
    "APPROVED_INDICES",
    "FORBIDDEN_QUERY_CLAUSES",
    "TemplateValidationError",
    "VendorQueryTemplate",
    "validate_template_query",
]


class VendorQueryTemplate(ABC):
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
