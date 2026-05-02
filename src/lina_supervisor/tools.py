"""Claude tool definitions exposed to the supervisor LLM.

The supervisor exposes one tool per worker subsystem (A, B, C). Each tool
takes a ``query_type`` from the subsystem's TEMPLATE_REGISTRY and a
``params`` object that matches the per-template Pydantic schema.
"""

from __future__ import annotations

from typing import Any

from lina_redshift.templates import TEMPLATE_REGISTRY as RS_REGISTRY
from lina_users.templates import TEMPLATE_REGISTRY as USERS_REGISTRY
from lina_vendors.templates import TEMPLATE_REGISTRY as VENDORS_REGISTRY


def build_tool_definitions() -> list[dict[str, Any]]:
    """Return the three Claude tool dicts in canonical order."""
    return [
        _tool_for_subsystem(
            name="query_redshift",
            description=(
                "Run a typed query against the legal_matter_spend Redshift store. "
                "Use for matter, vendor, timekeeper spend analytics; invoice or "
                "budget data; rate analysis. Specify a `query_type` from the "
                "catalog and structured `params`."
            ),
            registry=RS_REGISTRY,
        ),
        _tool_for_subsystem(
            name="search_users",
            description=(
                "Search corporate user profiles. Use for finding internal users by "
                "name, role, department, or to walk reporting chains."
            ),
            registry=USERS_REGISTRY,
        ),
        _tool_for_subsystem(
            name="search_vendors",
            description=(
                "Search outside counsel lawyer profiles. Use for finding vendor "
                "lawyers by name, vendor, practice area, jurisdiction, or "
                "hourly-rate band."
            ),
            registry=VENDORS_REGISTRY,
        ),
    ]


def _tool_for_subsystem(
    *,
    name: str,
    description: str,
    registry: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": sorted(registry.keys()),
                },
                "params": {
                    "type": "object",
                    "description": (
                        "Per-query_type parameter object; see template-specific "
                        "schemas in the system prompt."
                    ),
                },
            },
            "required": ["query_type", "params"],
        },
    }


def per_template_params_schemas() -> dict[str, dict[str, Any]]:
    """Return query_type → Params JSON schema for the system prompt."""
    out: dict[str, dict[str, Any]] = {}
    for registry in (RS_REGISTRY, USERS_REGISTRY, VENDORS_REGISTRY):
        for query_type, template in registry.items():
            out[query_type] = template.Params.model_json_schema()
    return out
