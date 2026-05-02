"""Fixtures for the lina_users OpenSearch integration suite (real AWS OpenSearch).

Tests in this directory are skipped automatically when `LINA_OPENSEARCH_HOST` is
not set, mirroring the pattern in `tests/integration/conftest.py` for Redshift.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

from lina_core.opensearch import open_client, resolve_config


@pytest.fixture(scope="session")
def aws_opensearch_host() -> str:
    host = os.environ.get("LINA_OPENSEARCH_HOST")
    if not host:
        pytest.skip("LINA_OPENSEARCH_HOST not set")
    return host


@pytest.fixture(scope="session")
def aws_opensearch_client(aws_opensearch_host: str) -> Iterator[Any]:
    config = resolve_config()
    client = open_client(config)
    try:
        yield client
    finally:
        # opensearch-py clients don't need explicit close; underlying transport
        # is closed at process exit. No-op for symmetry with redshift_conn.
        pass
