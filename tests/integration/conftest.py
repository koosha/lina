"""Fixtures specific to the integration suite (real Redshift Serverless)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg2
import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812


@pytest.fixture(scope="session")
def redshift_dsn() -> str:
    dsn = os.environ.get("LINA_REDSHIFT_DSN")
    if not dsn:
        pytest.skip("LINA_REDSHIFT_DSN not set")
    return dsn


@pytest.fixture(scope="session")
def redshift_conn(redshift_dsn: str) -> Iterator[PgConnection]:
    conn = psycopg2.connect(redshift_dsn)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()
