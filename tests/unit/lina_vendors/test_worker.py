"""Unit tests for VendorSearchWorker.

Uses an in-memory fake client to validate worker control flow without Docker.
"""

from __future__ import annotations

from typing import Any

import pytest

from lina_core.caller import CallerContext
from lina_vendors.packet import ErrorPacket, ResultPacket
from lina_vendors.worker import VendorSearchWorker


class _FakeClient:
    def __init__(
        self, hits: list[dict[str, Any]] | None = None, *, exc: Exception | None = None
    ) -> None:
        self._hits = hits or []
        self._exc = exc
        self.calls: list[dict[str, Any]] = []

    def search(self, *, index: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"index": index, "body": body, "kwargs": kwargs})
        if self._exc is not None:
            raise self._exc
        return {"hits": {"hits": self._hits}}


def _caller(*roles: str) -> CallerContext:
    return CallerContext(
        user_id="caller_test",
        roles=frozenset(roles),
        request_id="req_test",
    )


@pytest.mark.unit
def test_run_unknown_template_returns_error_packet() -> None:
    worker = VendorSearchWorker(client=_FakeClient())
    result = worker.run(
        query_type="not_a_real_template",
        params={},
        caller=_caller("legal_ops"),
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "UnknownTemplateError"


@pytest.mark.unit
def test_run_authorization_failure_returns_error_packet() -> None:
    worker = VendorSearchWorker(client=_FakeClient())
    result = worker.run(
        query_type="outside_counsel_filter",
        params={"vendor_id": ["vendor_walker"]},
        caller=_caller("billing_clerk"),  # not legal_ops/finance/procurement
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "AuthorizationError"


@pytest.mark.unit
def test_run_invalid_params_returns_error_packet() -> None:
    worker = VendorSearchWorker(client=_FakeClient())
    result = worker.run(
        query_type="timekeeper_lookup",
        params={},  # zero of timekeeper_id/email/vendor_id provided
        caller=_caller("any_role"),
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "InvalidParametersError"


@pytest.mark.unit
def test_run_timekeeper_lookup_returns_shaped_result_packet() -> None:
    fake = _FakeClient(
        hits=[
            {
                "_source": {
                    "timekeeper_id": "tk_walker_partner",
                    "display_name": "Patricia Walker",
                    "vendor_name": "Walker & Associates LLP",
                    "internal_secret": "redacted",
                }
            }
        ]
    )
    worker = VendorSearchWorker(client=fake)
    result = worker.run(
        query_type="timekeeper_lookup",
        params={"timekeeper_id": "tk_walker_partner"},
        caller=_caller("any_role"),
    )
    assert isinstance(result, ResultPacket)
    assert result.row_count == 1
    assert result.metrics == [
        {
            "timekeeper_id": "tk_walker_partner",
            "display_name": "Patricia Walker",
            "vendor_name": "Walker & Associates LLP",
        }
    ]
    assert fake.calls[0]["index"] == "vendor_lawyer_profiles_v1"


@pytest.mark.unit
def test_run_maps_connection_error_to_backend_connection_error() -> None:
    from opensearchpy.exceptions import ConnectionError as OSConnectionError

    fake = _FakeClient(exc=OSConnectionError(599, "conn refused", {}))
    worker = VendorSearchWorker(client=fake)
    result = worker.run(
        query_type="timekeeper_lookup",
        params={"timekeeper_id": "tk1"},
        caller=_caller("any_role"),
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "BackendConnectionError"


@pytest.mark.unit
def test_run_maps_timeout_request_error_to_query_timeout_error() -> None:
    from opensearchpy.exceptions import RequestError

    fake = _FakeClient(exc=RequestError(408, "request timed_out", {"error": "timed_out"}))
    worker = VendorSearchWorker(client=fake)
    result = worker.run(
        query_type="timekeeper_lookup",
        params={"timekeeper_id": "tk1"},
        caller=_caller("any_role"),
    )
    assert isinstance(result, ErrorPacket)
    assert result.error.type == "QueryTimeoutError"
