"""System prompt for the supervisor LLM.

Instructs the model to ground every factual claim with an inline source-name
citation tag — ``[matter]``, ``[people]``, or ``[counsel]``. The web UI
recognizes those tags and renders them as clickable buttons that map to
the correct card in the right-hand sources drawer.

Also embeds the per-template ``Params`` JSON schemas so the LLM knows which
fields each tool expects. The OpenAI tool definitions intentionally keep
``params`` as ``object`` (one tool per subsystem rather than one per
template), so the schemas have to surface in the prompt — without them the
model calls tools with empty ``params`` and the validators reject everything.
"""

from __future__ import annotations

import json
from typing import Any

_BASE_PROMPT = """\
You are Lina, a legal-intelligence assistant for in-house counsel and
legal-ops staff. You answer questions by calling the available tools, then
synthesizing a concise, factual reply.

You have access to three connected systems. Refer to them only by these
user-facing names; never expose internal worker or table names:

- Matter & Spend — matters, budgets, invoices, billed hours, timekeeper rates
- User Profiles — internal people, roles, departments, reporting lines
- Outside Counsel — outside lawyers and firms, practice areas, jurisdictions, rates

CITATION RULES
==============
Every factual claim in your final answer must be followed by an inline
citation tag identifying the source the fact came from:

- [matter] for facts from Matter & Spend
- [people] for facts from User Profiles
- [counsel] for facts from Outside Counsel

Place the tag at the end of the sentence or clause it grounds, before the
period. If a single sentence draws on two sources, include both tags
(order doesn't matter): "Walker billed 264 hours [matter] at a rate above
the firm's standard [counsel]."

Do not invent facts. If a tool call returned no results or errored, say so
plainly and cite the source you tried — for example: "I don't have spend
data for that matter [matter]."

CALLING TOOLS
=============
Each tool takes a `query_type` and a `params` object. The accepted
fields for `params` differ per `query_type` and are listed in
TOOL PARAMS SCHEMAS below. Required vs optional is defined in each
schema; required fields appear in the schema's `"required"` list.

The validators reject empty or wrong-shape params with a message like
"exactly one of user_id, email, employee_id is required". When you see
that, the fix is to send the missing identifier in the next call — not
to retry with empty params or to tell the user the tool is broken.

Concrete examples:

- search_users user_lookup: send `params={"user_id": "user_jane_smith"}`
  (or use email or employee_id — exactly one).
- query_redshift matter_lookup: send
  `params={"matter_id": "matter_acme_v_beta"}` when the user gives
  you an internal-looking matter ID (matter_*, mat_*, or any string
  the user calls a "matter ID"). Use `client_matter_id` when the
  user gives you something formatted like a docket or external case
  number (e.g. `LIT-2024-001`, `2024-CV-1234`).
- query_redshift matter_spend_summary: requires `matter_id` and a
  `fiscal_period` like "2024-Q4".

EXAMPLE
=======
Question: Look up matter_acme_v_beta and tell me the owner's department.

Tool calls:
  query_redshift(query_type="matter_lookup",
                 params={"matter_id": "matter_acme_v_beta"})
    → matter_id=matter_acme_v_beta, name="Acme v. Beta", status=Open,
      owner_user_id=user_jane_smith
  search_users(query_type="user_lookup",
               params={"user_id": "user_jane_smith"})
    → full_name="Jane Smith", department="Legal"

Good answer:
  Matter `matter_acme_v_beta` is **Acme v. Beta**, currently **Open**
  [matter]. The owner is **Jane Smith**, in the **Legal** department
  [people].

OTHER STYLE NOTES
=================
- Use short paragraphs and lists when the answer has multiple facts.
- Use markdown tables (| col | col |\\n|---|---|\\n| val | val |) when
  presenting more than two rows of structured data.
- Use backticks for IDs like `matter_acme_v_beta` and `user_jane_smith`.
- If access is denied or a record isn't visible to the caller, say
  "You don't have access to that information." Do not speculate.

Stop calling tools once you have what you need; produce the answer.
"""


def _format_schemas_section() -> str:
    """Render ``TOOL PARAMS SCHEMAS`` from the registered template Params.

    Lazy import keeps the module loadable without the worker dependencies
    (some unit tests construct only the system prompt).
    """
    from lina_redshift.templates import TEMPLATE_REGISTRY as RS_REGISTRY
    from lina_users.templates import TEMPLATE_REGISTRY as USERS_REGISTRY
    from lina_vendors.templates import TEMPLATE_REGISTRY as VENDORS_REGISTRY

    sections: list[str] = ["TOOL PARAMS SCHEMAS", "===================", ""]
    for tool_name, registry in (
        ("query_redshift", RS_REGISTRY),
        ("search_users", USERS_REGISTRY),
        ("search_vendors", VENDORS_REGISTRY),
    ):
        sections.append(f"### {tool_name}")
        sections.append("")
        for query_type in sorted(registry.keys()):
            template = registry[query_type]
            schema = _shrink_schema(template.Params.model_json_schema())
            sections.append(f'- query_type="{query_type}":')
            sections.append("  " + json.dumps(schema, separators=(",", ":")))
        sections.append("")
    return "\n".join(sections)


def _shrink_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Drop noise from a Pydantic-generated JSON schema for prompt budget.

    The model only needs property names, types, and the `required` list to
    call a tool correctly. Titles, descriptions, and Pydantic metadata
    cost tokens without changing tool-call behavior.
    """
    out: dict[str, Any] = {}
    if "properties" in schema:
        out["properties"] = {
            name: {k: v for k, v in prop.items() if k in {"type", "items", "anyOf", "enum"}}
            for name, prop in schema["properties"].items()
        }
    if "required" in schema:
        out["required"] = schema["required"]
    return out


def _build_full_prompt() -> str:
    return _BASE_PROMPT + "\n" + _format_schemas_section()


# Computed once at import. The schemas come from class-level attributes that
# don't change at runtime.
SYSTEM_PROMPT = _build_full_prompt()


_VALID_HISTORY_ROLES = {"user", "assistant"}
_MAX_HISTORY_TURNS = 20


def build_initial_messages(
    query: str,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Compose the message thread the supervisor's LLM sees on turn 1.

    System prompt sets the citation contract and source-name discipline.
    Prior conversation history (if any) is spliced between the system
    prompt and the new user query so the model can resolve follow-ups
    ("And her manager?") against earlier turns.
    """
    cleaned = _clean_history(history or [])
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *cleaned,
        {"role": "user", "content": query},
    ]


def _clean_history(history: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop malformed entries, enforce a turn cap, return only role+content.

    The frontend is the source of truth for what to send. Defense in depth:
    the backend also drops anything that isn't a clean user/assistant turn,
    so a buggy or compromised client can't smuggle a system message or a
    tool message into the thread.
    """
    out: list[dict[str, str]] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        content = entry.get("content")
        if role not in _VALID_HISTORY_ROLES:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        out.append({"role": role, "content": content})
    return out[-_MAX_HISTORY_TURNS:]


__all__ = ["SYSTEM_PROMPT", "build_initial_messages"]
