"""Unit tests for lina_users.packet."""

from __future__ import annotations

import json

import pytest

from lina_core.errors import AuthorizationError
from lina_users.packet import ErrorPacket, ResultPacket


@pytest.mark.unit
def test_result_packet_defaults_source_engine_and_schema() -> None:
    packet = ResultPacket(
        result_type="user_lookup",
        metrics=[],
        sql_trace_id="01J",
        row_count=0,
    )
    assert packet.source_engine == "opensearch"
    assert packet.schema_name == "corp_user_profiles_v1"
    assert packet.truncated is False


@pytest.mark.unit
def test_result_packet_serializes_with_alias() -> None:
    packet = ResultPacket(
        result_type="user_search",
        metrics=[{"user_id": "u1"}],
        sql_trace_id="01J",
        row_count=1,
        truncated=True,
    )
    blob = json.loads(packet.model_dump_json(by_alias=True))
    assert blob["schema"] == "corp_user_profiles_v1"
    assert blob["source_engine"] == "opensearch"


@pytest.mark.unit
def test_error_packet_from_exception_carries_type_and_message() -> None:
    exc = AuthorizationError("missing role legal_ops")
    err = ErrorPacket.from_exception(exc, sql_trace_id="01J", result_type="manager_chain")
    assert err.error.type == "AuthorizationError"
    assert err.error.message == "missing role legal_ops"
    assert err.result_type == "manager_chain"
    assert err.source_engine == "opensearch"
    assert err.schema_name == "corp_user_profiles_v1"


@pytest.mark.unit
def test_error_packet_serializes_with_alias() -> None:
    exc = AuthorizationError("nope")
    err = ErrorPacket.from_exception(exc, sql_trace_id="01J", result_type="user_lookup")
    blob = json.loads(err.model_dump_json(by_alias=True))
    assert blob["schema"] == "corp_user_profiles_v1"
    assert blob["error"]["type"] == "AuthorizationError"
