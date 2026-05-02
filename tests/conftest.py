"""Shared pytest fixtures for unit and integration suites."""

from __future__ import annotations

import os
from collections.abc import Iterator

import psycopg2
import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812
from pytest_postgresql import factories

postgresql_proc = factories.postgresql_proc(
    port=None,
    unixsocketdir="/tmp",
    executable="/usr/local/opt/postgresql@16/bin/pg_ctl",
)
postgresql_db = factories.postgresql("postgresql_proc", dbname="lina_test")


@pytest.fixture
def pg_dsn(postgresql_db: PgConnection) -> str:
    """DSN for the per-test Postgres database."""
    info = postgresql_db.info
    return f"postgresql://{info.user}@{info.host}:{info.port}/{info.dbname}"


@pytest.fixture
def pg_conn(pg_dsn: str) -> Iterator[PgConnection]:
    conn = psycopg2.connect(pg_dsn)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests when LINA_REDSHIFT_DSN is unset."""
    if os.environ.get("LINA_REDSHIFT_DSN"):
        return
    skip_integration = pytest.mark.skip(reason="LINA_REDSHIFT_DSN not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
