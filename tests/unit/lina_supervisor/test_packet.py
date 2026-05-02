"""Unit tests for SupervisorResponse."""

from __future__ import annotations

import json

import pytest

from lina_supervisor.packet import SupervisorResponse


@pytest.mark.unit
def test_default_values() -> None:
    resp = SupervisorResponse(
        session_id="s1",
        request_id="r1",
        user_id="user_jane",
        answer_text="hi",
        model="gpt-4o",
        duration_ms=42,
        sql_trace_id="01J0000000000000000000000",
    )
    assert resp.source_engine == "supervisor"
    assert resp.worker_packets == []
    assert resp.worker_call_count == 0
    assert resp.truncated is False


@pytest.mark.unit
def test_required_fields_validation() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SupervisorResponse(
            session_id="s1",
            request_id="r1",
            # user_id missing
            answer_text="hi",
            model="gpt-4o",
            duration_ms=42,
            sql_trace_id="01J0000000000000000000000",
        )  # type: ignore[call-arg]


@pytest.mark.unit
def test_round_trips_via_json() -> None:
    resp = SupervisorResponse(
        session_id="s1",
        request_id="r1",
        user_id="user_jane",
        answer_text="answer",
        worker_packets=[{"foo": "bar"}],
        worker_call_count=1,
        truncated=True,
        model="gpt-4o",
        duration_ms=100,
        sql_trace_id="01J0000000000000000000000",
    )
    payload = json.loads(resp.model_dump_json())
    assert payload["source_engine"] == "supervisor"
    assert payload["worker_packets"] == [{"foo": "bar"}]
    assert payload["truncated"] is True
    parsed = SupervisorResponse.model_validate(payload)
    assert parsed == resp
