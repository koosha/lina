"""Smoke tests for UserSearchWorker against a live AWS OpenSearch domain.

Requires:
- `LINA_OPENSEARCH_HOST` exported.
- `LINA_OPENSEARCH_AUTH=aws_sigv4` (typical for AWS OpenSearch) plus
  `LINA_AWS_REGION`, or `basic` with `LINA_OPENSEARCH_USER`/`LINA_OPENSEARCH_PASSWORD`.
- Indices and seed already applied
  (run `lina-users indices apply && lina-users seed`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lina_core.caller import CallerContext
from lina_users.indices.runner import IndexRunner
from lina_users.packet import ResultPacket
from lina_users.worker import UserSearchWorker


@pytest.fixture
def legal_ops_caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane_smith",
        roles=frozenset({"legal_ops"}),
        request_id="integration_req",
    )


def _mappings_dir() -> Path:
    from importlib import resources

    return Path(str(resources.files("lina_users.indices").joinpath("mappings")))


@pytest.mark.integration
def test_indices_apply_against_aws_opensearch(aws_opensearch_client: Any) -> None:
    runner = IndexRunner(client=aws_opensearch_client, mappings_dir=_mappings_dir())
    # Idempotent: second apply should be a no-op.
    runner.apply_pending()
    second = runner.apply_pending()
    assert second == []


@pytest.mark.integration
def test_user_lookup_against_aws_opensearch(
    aws_opensearch_client: Any,
    legal_ops_caller: CallerContext,
) -> None:
    worker = UserSearchWorker(client=aws_opensearch_client)
    packet = worker.run(
        query_type="user_lookup",
        params={"user_id": "user_jane_smith"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 1
    assert packet.metrics[0]["user_id"] == "user_jane_smith"


@pytest.mark.integration
def test_user_search_against_aws_opensearch(
    aws_opensearch_client: Any,
    legal_ops_caller: CallerContext,
) -> None:
    worker = UserSearchWorker(client=aws_opensearch_client)
    packet = worker.run(
        query_type="user_search",
        params={"query": "Counsel", "department": ["Legal"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count > 0


@pytest.mark.integration
def test_people_filter_against_aws_opensearch(
    aws_opensearch_client: Any,
    legal_ops_caller: CallerContext,
) -> None:
    worker = UserSearchWorker(client=aws_opensearch_client)
    packet = worker.run(
        query_type="people_filter",
        params={"department": ["Legal"], "user_status": ["active"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count > 0
