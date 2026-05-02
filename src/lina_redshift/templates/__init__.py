"""Typed catalog of read-only query templates.

Importing this module triggers AST validation of every registered template.
"""

from __future__ import annotations

from lina_redshift.templates.base import QueryTemplate

# Registry is populated by register_template_module() below.
TEMPLATE_REGISTRY: dict[str, QueryTemplate] = {}


def register(template: QueryTemplate) -> QueryTemplate:
    """Register a template instance and run its AST sanity check."""
    if template.query_type in TEMPLATE_REGISTRY:
        raise ValueError(f"duplicate query_type: {template.query_type}")
    template.validate_at_import()
    TEMPLATE_REGISTRY[template.query_type] = template
    return template


def get_template(query_type: str) -> QueryTemplate:
    from lina_redshift.errors import UnknownTemplateError

    try:
        return TEMPLATE_REGISTRY[query_type]
    except KeyError as exc:
        raise UnknownTemplateError(f"no template registered for {query_type!r}") from exc


def all_templates() -> list[QueryTemplate]:
    return list(TEMPLATE_REGISTRY.values())


from lina_redshift.templates.matter_lookup import MatterLookupTemplate  # noqa: E402
from lina_redshift.templates.matter_spend_summary import MatterSpendSummaryTemplate  # noqa: E402

register(MatterLookupTemplate())
register(MatterSpendSummaryTemplate())
