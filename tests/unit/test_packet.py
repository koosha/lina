"""Unit tests for ResultPacket and error mapping."""

from __future__ import annotations

import json

import pytest

from lina_redshift.errors import (
    AuthorizationError,
    InvalidParametersError,
    UnknownTemplateError,
    WorkerInternalError,
)
from lina_redshift.packet import ErrorPacket, ResultPacket


@pytest.mark.unit
def test_result_packet_serializes_with_schema_alias() -> None:
    p = ResultPacket(
        result_type="matter_lookup",
        metrics=[{"matter_id": "m1"}],
        sql_trace_id="01HZX0",
        row_count=1,
        truncated=False,
    )
    data = p.model_dump(by_alias=True)

    assert data["source_engine"] == "redshift"
    assert data["schema"] == "legal_matter_spend"  # aliased from schema_name
    assert data["result_type"] == "matter_lookup"
    assert data["sql_trace_id"] == "01HZX0"
    assert data["truncated"] is False


@pytest.mark.unit
def test_result_packet_round_trip_json() -> None:
    p = ResultPacket(
        result_type="matter_spend_summary",
        metrics=[{"matter_id": "m1", "fiscal_period": "2024-Q1"}],
        sql_trace_id="01HZX0",
        row_count=1,
        truncated=True,
    )
    raw = p.model_dump_json(by_alias=True)
    parsed = json.loads(raw)
    assert parsed["truncated"] is True
    assert parsed["row_count"] == 1


@pytest.mark.unit
def test_error_packet_shape() -> None:
    err = ErrorPacket.from_exception(
        AuthorizationError("missing role 'finance'"),
        sql_trace_id="01HZX0",
        result_type="vendor_spend_summary",
    )
    data = err.model_dump(by_alias=True)
    assert data["source_engine"] == "redshift"
    assert data["error"]["type"] == "AuthorizationError"
    assert "finance" in data["error"]["message"]
    assert data["sql_trace_id"] == "01HZX0"


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc,expected_type",
    [
        (UnknownTemplateError("bad"), "UnknownTemplateError"),
        (AuthorizationError("nope"), "AuthorizationError"),
        (InvalidParametersError("bad params"), "InvalidParametersError"),
        (WorkerInternalError("boom"), "WorkerInternalError"),
    ],
)
def test_error_packet_maps_each_exception_type(
    exc: Exception, expected_type: str,
) -> None:
    err = ErrorPacket.from_exception(exc, sql_trace_id="t", result_type="x")
    assert err.error.type == expected_type
