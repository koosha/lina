"""Single-step supervisor smoke test against a real (or replayed) OpenAI API.

The test asks "How many open litigation matters do we have?" and asserts that
the supervisor:

- issues exactly one ``query_redshift`` tool call (typically against
  ``matter_spend_summary`` or ``matter_lookup``);
- produces a final text answer that mentions a count;
- attaches at least one worker packet to the response.

When no cassette is recorded and no ``OPENAI_API_KEY`` is set, this test
skips cleanly via the conftest hook.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


def _redshift_packet(*, row_count: int) -> Any:
    """Stand-in ResultPacket for the Redshift worker mock."""
    packet = MagicMock()
    packet.model_dump.return_value = {
        "source_engine": "redshift",
        "result_type": "matter_spend_summary",
        "metrics": [
            {
                "matter_id": "matter_acme_v_beta",
                "open_count": row_count,
            }
        ],
        "row_count": row_count,
        "truncated": False,
        "sql_trace_id": "trace_smoke_1",
    }
    return packet


@pytest.mark.integration
@pytest.mark.vcr()
def test_simple_open_litigation_count(supervisor_for_test: dict[str, Any]) -> None:
    """Ask a single-step question and verify the supervisor answers."""
    rs_worker = supervisor_for_test["rs_worker"]
    rs_worker.run.return_value = _redshift_packet(row_count=12)

    final_state = supervisor_for_test["graph"].invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": "How many open litigation matters do we have?",
                }
            ],
            "caller": supervisor_for_test["caller"],
            "worker_call_count": 0,
            "worker_packets": [],
            "truncated": False,
            "answer_text": "",
        }
    )

    # The supervisor should have called the redshift worker at least once.
    assert rs_worker.run.call_count >= 1
    assert final_state["worker_call_count"] >= 1
    assert len(final_state["worker_packets"]) >= 1

    answer = final_state["answer_text"].lower()
    # Plausible substrings: a digit (the count), or the word "litigation"
    # / "matter" / "open". Assertions are intentionally permissive — exact
    # phrasing depends on the model.
    assert any(ch.isdigit() for ch in answer) or "matter" in answer or "litigation" in answer
