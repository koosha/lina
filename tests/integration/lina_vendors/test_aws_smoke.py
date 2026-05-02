"""Smoke tests for VendorSearchWorker against a live AWS OpenSearch domain.

Requires:
- `LINA_OPENSEARCH_HOST` exported.
- `LINA_OPENSEARCH_AUTH=aws_sigv4` (typical for AWS OpenSearch) plus
  `LINA_AWS_REGION`, or `basic` with `LINA_OPENSEARCH_USER`/`LINA_OPENSEARCH_PASSWORD`.
- Indices and seed already applied
  (run `lina-vendors indices apply && lina-vendors seed`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lina_core.caller import CallerContext
from lina_vendors.indices.runner import IndexRunner
from lina_vendors.packet import ResultPacket
from lina_vendors.worker import VendorSearchWorker


@pytest.fixture
def legal_ops_caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane_smith",
        roles=frozenset({"legal_ops"}),
        request_id="integration_req",
    )


def _mappings_dir() -> Path:
    from importlib import resources

    return Path(str(resources.files("lina_vendors.indices").joinpath("mappings")))


@pytest.mark.integration
def test_indices_apply_against_aws_opensearch(aws_opensearch_client: Any) -> None:
    runner = IndexRunner(client=aws_opensearch_client, mappings_dir=_mappings_dir())
    # Idempotent: second apply should be a no-op.
    runner.apply_pending()
    second = runner.apply_pending()
    assert second == []


@pytest.mark.integration
def test_timekeeper_lookup_against_aws_opensearch(
    aws_opensearch_client: Any,
    legal_ops_caller: CallerContext,
) -> None:
    worker = VendorSearchWorker(client=aws_opensearch_client)
    packet = worker.run(
        query_type="timekeeper_lookup",
        params={"timekeeper_id": "tk_walker_partner"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 1
    assert packet.metrics[0]["timekeeper_id"] == "tk_walker_partner"


@pytest.mark.integration
def test_lawyer_search_against_aws_opensearch(
    aws_opensearch_client: Any,
    legal_ops_caller: CallerContext,
) -> None:
    worker = VendorSearchWorker(client=aws_opensearch_client)
    packet = worker.run(
        query_type="lawyer_search",
        params={"query": "Litigation", "active_status": ["active"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count > 0


@pytest.mark.integration
def test_outside_counsel_filter_against_aws_opensearch(
    aws_opensearch_client: Any,
    legal_ops_caller: CallerContext,
) -> None:
    worker = VendorSearchWorker(client=aws_opensearch_client)
    packet = worker.run(
        query_type="outside_counsel_filter",
        params={"vendor_id": ["vendor_walker"], "currency_code": "USD"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count > 0
