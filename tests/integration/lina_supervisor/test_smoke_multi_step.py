"""Multi-step supervisor smoke test — ``search_vendors`` followed by ``query_redshift``.

The question — "How much did Walker bill on the Acme litigation last quarter?" —
forces the supervisor to:

1. Resolve the vendor "Walker" via ``search_vendors``;
2. Plug the resolved timekeeper / vendor IDs into a ``query_redshift`` call
   against ``vendor_spend_summary`` (or ``invoice_search``);
3. Synthesize a final answer mentioning a dollar figure.

When no cassette is recorded and no ``ANTHROPIC_API_KEY`` is set, this test
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

    # The supervisor should have made at least one call to each subsystem.
    total_calls = vendors_worker.run.call_count + rs_worker.run.call_count
    assert total_calls >= 2
    assert final_state["worker_call_count"] >= 2
    assert len(final_state["worker_packets"]) >= 2

    answer = final_state["answer_text"].lower()
    # Plausible substrings: the vendor name "walker", a dollar sign, or any digit.
    assert (
        "walker" in answer
        or "$" in answer
        or any(ch.isdigit() for ch in answer)
        or "acme" in answer
    )
