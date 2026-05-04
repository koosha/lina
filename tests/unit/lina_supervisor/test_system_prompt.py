"""Tests for the supervisor system prompt construction.

The prompt is the only signal the LLM has about which fields each tool
accepts (the OpenAI tool definition keeps `params` as opaque `object`).
If the schemas drift out of the prompt the supervisor reverts to calling
tools with empty params — see docs/known-issues.md for the incident.
"""

from __future__ import annotations

import json

import pytest

from lina_supervisor.system_prompt import SYSTEM_PROMPT, build_initial_messages


@pytest.mark.unit
def test_system_prompt_lists_all_three_tool_sections() -> None:
    assert "### query_redshift" in SYSTEM_PROMPT
    assert "### search_users" in SYSTEM_PROMPT
    assert "### search_vendors" in SYSTEM_PROMPT


@pytest.mark.unit
def test_user_lookup_schema_advertises_all_three_identifiers() -> None:
    """Prevents regression of the 'tool rejects user_id' bug.

    The validator on `UserLookupParams` requires exactly one of `user_id`,
    `email`, `employee_id`. The LLM only knows that because the prompt
    advertises the schema. If the schema goes missing, the LLM calls
    user_lookup with empty params and the validator rejects every call.
    """
    marker = '- query_type="user_lookup":'
    assert marker in SYSTEM_PROMPT
    line = SYSTEM_PROMPT.split(marker, 1)[1].splitlines()[1].strip()
    schema = json.loads(line)
    props = schema["properties"]
    assert "user_id" in props
    assert "email" in props
    assert "employee_id" in props


@pytest.mark.unit
def test_matter_lookup_schema_present() -> None:
    """The other end of the demo's main composition. Same reasoning."""
    marker = '- query_type="matter_lookup":'
    assert marker in SYSTEM_PROMPT
    line = SYSTEM_PROMPT.split(marker, 1)[1].splitlines()[1].strip()
    schema = json.loads(line)
    props = schema["properties"]
    assert "matter_id" in props
    assert "client_matter_id" in props


@pytest.mark.unit
def test_build_initial_messages_uses_full_prompt() -> None:
    msgs = build_initial_messages("Look up matter_acme_v_beta")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == SYSTEM_PROMPT
    assert msgs[-1] == {"role": "user", "content": "Look up matter_acme_v_beta"}


@pytest.mark.unit
def test_build_initial_messages_splices_history() -> None:
    history = [
        {"role": "user", "content": "What is Jane's department?"},
        {"role": "assistant", "content": "Jane is in Legal [people]."},
    ]
    msgs = build_initial_messages("And her manager?", history=history)
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[-1]["content"] == "And her manager?"


@pytest.mark.unit
def test_history_drops_malformed_entries() -> None:
    bad: list = [
        {"role": "system", "content": "should be dropped"},
        {"role": "user", "content": ""},
        {"role": "tool", "content": "should be dropped"},
        "not a dict",
        {"role": "user", "content": "kept"},
    ]
    msgs = build_initial_messages("now", history=bad)
    user_turns = [m for m in msgs if m["role"] == "user"]
    # One from history (kept) plus the new query.
    assert [m["content"] for m in user_turns] == ["kept", "now"]
    assert all(m["role"] != "tool" for m in msgs)
    assert sum(1 for m in msgs if m["role"] == "system") == 1
