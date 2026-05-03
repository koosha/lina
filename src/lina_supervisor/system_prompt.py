"""System prompt for the supervisor LLM.

Instructs the model to ground every factual claim with an inline source-name
citation tag — ``[matter]``, ``[people]``, or ``[counsel]``. The web UI
recognizes those tags and renders them as clickable buttons that map to
the correct card in the right-hand sources drawer.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
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

EXAMPLE
=======
Question: Look up matter_acme_v_beta and tell me the owner's department.

Tool calls return:
  - matter_lookup: matter_id=matter_acme_v_beta, name="Acme v. Beta",
    status=Open, owner_user_id=user_jane_smith
  - user_lookup: user_id=user_jane_smith, full_name="Jane Smith",
    department="Legal"

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
