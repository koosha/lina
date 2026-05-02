"""Typed catalog of read-only OpenSearch query templates for Subsystem A.

Importing this module triggers DSL validation of every registered template.
"""

from __future__ import annotations

from lina_users.templates.base import UserQueryTemplate

# Registry is populated by template module imports below.
TEMPLATE_REGISTRY: dict[str, UserQueryTemplate] = {}


def register(template: UserQueryTemplate) -> UserQueryTemplate:
    """Register a template instance and run its DSL sanity check."""
    if template.query_type in TEMPLATE_REGISTRY:
        raise ValueError(f"duplicate query_type: {template.query_type}")
    template.validate_at_import()
    TEMPLATE_REGISTRY[template.query_type] = template
    return template


def get_template(query_type: str) -> UserQueryTemplate:
    from lina_core.errors import UnknownTemplateError

    try:
        return TEMPLATE_REGISTRY[query_type]
    except KeyError as exc:
        raise UnknownTemplateError(f"no template registered for {query_type!r}") from exc


def all_templates() -> list[UserQueryTemplate]:
    return list(TEMPLATE_REGISTRY.values())


from lina_users.templates.manager_chain import ManagerChainTemplate  # noqa: E402
from lina_users.templates.people_filter import PeopleFilterTemplate  # noqa: E402
from lina_users.templates.user_lookup import UserLookupTemplate  # noqa: E402
from lina_users.templates.user_search import UserSearchTemplate  # noqa: E402

register(UserLookupTemplate())
register(UserSearchTemplate())
register(ManagerChainTemplate())
register(PeopleFilterTemplate())
