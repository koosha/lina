"""Multi-step supervisor smoke test — vendor / spend question routed by the LLM.

The question — "How much did Walker bill on the Acme litigation last quarter?" —
exercises the supervisor's tool-routing surface. A capable model may choose
to either:

- Chain ``search_vendors`` → ``query_redshift`` (two tool calls), or
- Go directly to ``query_redshift`` if the vendor name is already enough to
  build a typed query (one tool call). Newer reasoning-aware models tend to
  pick this path.

Either route is acceptable; the supervisor's job is to dispatch *some* tool
call and produce a synthesized answer that mentions plausible substance
(vendor name, dollar figure, matter name, or a digit).

When no cassette is recorded and no ``OPENAI_API_KEY`` is set, this test
skips cleanly via the conftest hook.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


def _vendors_packet() -> Any:
    """Stand-in ResultPacket for the vendors worker mock."""
    packet = MagicMock()
    packet.model_dump.return_value = {
        "source_engine": "opensearch",
        "result_type": "lawyer_search",
        "metrics": [
            {
                "timekeeper_id": "tk_walker_partner",
                "vendor_id": "vendor_walker",
                "name": "Walker, J.",
                "rate_band": "partner",
            }
        ],
        "row_count": 1,
        "truncated": False,
        "sql_trace_id": "trace_smoke_vendor",
    }
    return packet


def _redshift_packet() -> Any:
    """Stand-in ResultPacket for the Redshift worker mock."""
    packet = MagicMock()
    packet.model_dump.return_value = {
        "source_engine": "redshift",
        "result_type": "vendor_spend_summary",
        "metrics": [
            {
                "vendor_id": "vendor_walker",
                "fiscal_period": "2024-Q4",
                "billed_amount_usd": 487_500.00,
                "matter_id": "matter_acme_v_beta",
            }
        ],
        "row_count": 1,
        "truncated": False,
        "sql_trace_id": "trace_smoke_spend",
    }
    return packet


@pytest.mark.integration
@pytest.mark.vcr()
def test_multi_step_walker_acme_spend(supervisor_for_test: dict[str, Any]) -> None:
    """Two-step query: vendor lookup → spend summary."""
    vendors_worker = supervisor_for_test["vendors_worker"]
    rs_worker = supervisor_for_test["rs_worker"]
    vendors_worker.run.return_value = _vendors_packet()
    rs_worker.run.return_value = _redshift_packet()

    final_state = supervisor_for_test["graph"].invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": ("How much did Walker bill on the Acme litigation last quarter?"),
                }
            ],
            "caller": supervisor_for_test["caller"],
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )

    # The supervisor must have dispatched at least one tool call. Capable
    # models may chain (vendors_worker + rs_worker) or one-shot directly to
    # rs_worker — both are valid routing decisions.
    total_calls = vendors_worker.run.call_count + rs_worker.run.call_count
    assert total_calls >= 1
    assert final_state["worker_call_count"] >= 1
    assert len(final_state["worker_packets"]) >= 1

    answer = final_state["answer_text"].lower()
    # Plausible substrings: the vendor name "walker", a dollar sign, or any digit.
    assert (
        "walker" in answer
        or "$" in answer
        or any(ch.isdigit() for ch in answer)
        or "acme" in answer
    )
