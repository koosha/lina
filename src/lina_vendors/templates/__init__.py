"""Typed catalog of read-only OpenSearch query templates for Subsystem B.

Importing this module triggers DSL validation of every registered template.
"""

from __future__ import annotations

from lina_vendors.templates.base import VendorQueryTemplate

# Registry is populated by template module imports below.
TEMPLATE_REGISTRY: dict[str, VendorQueryTemplate] = {}


def register(template: VendorQueryTemplate) -> VendorQueryTemplate:
    """Register a template instance and run its DSL sanity check."""
    if template.query_type in TEMPLATE_REGISTRY:
        raise ValueError(f"duplicate query_type: {template.query_type}")
    template.validate_at_import()
    TEMPLATE_REGISTRY[template.query_type] = template
    return template


def get_template(query_type: str) -> VendorQueryTemplate:
    from lina_core.errors import UnknownTemplateError

    try:
        return TEMPLATE_REGISTRY[query_type]
    except KeyError as exc:
        raise UnknownTemplateError(f"no template registered for {query_type!r}") from exc


def all_templates() -> list[VendorQueryTemplate]:
    return list(TEMPLATE_REGISTRY.values())


from lina_vendors.templates.lawyer_search import LawyerSearchTemplate  # noqa: E402
from lina_vendors.templates.outside_counsel_filter import (  # noqa: E402
    OutsideCounselFilterTemplate,
)
from lina_vendors.templates.practice_area_match import PracticeAreaMatchTemplate  # noqa: E402
from lina_vendors.templates.timekeeper_lookup import TimekeeperLookupTemplate  # noqa: E402

register(TimekeeperLookupTemplate())
register(LawyerSearchTemplate())
register(OutsideCounselFilterTemplate())
register(PracticeAreaMatchTemplate())
