"""Shared pytest fixtures for unit and integration suites."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from typing import Any

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
    """Skip integration tests whose backing service env var is unset.

    - Tests under `tests/integration/lina_users` and `tests/integration/lina_vendors`
      target AWS OpenSearch and require `LINA_OPENSEARCH_HOST`.
    - All other integration tests target Redshift and require `LINA_REDSHIFT_DSN`.
    """
    has_redshift = bool(os.environ.get("LINA_REDSHIFT_DSN"))
    has_opensearch = bool(os.environ.get("LINA_OPENSEARCH_HOST"))
    skip_redshift = pytest.mark.skip(reason="LINA_REDSHIFT_DSN not set")
    skip_opensearch = pytest.mark.skip(reason="LINA_OPENSEARCH_HOST not set")
    for item in items:
        if "integration" not in item.keywords:
            continue
        path = str(item.fspath)
        is_opensearch_suite = (
            "/integration/lina_users/" in path or "/integration/lina_vendors/" in path
        )
        if is_opensearch_suite:
            if not has_opensearch:
                item.add_marker(skip_opensearch)
        elif not has_redshift:
            item.add_marker(skip_redshift)


@pytest.fixture(scope="session")
def opensearch_container() -> Iterator[Any]:
    """Spin up a single OpenSearch container per test session.

    Skips when testcontainers[opensearch] is unavailable or when the local
    Docker daemon is not running.
    """
    try:
        from testcontainers.opensearch import OpenSearchContainer
    except ImportError:
        pytest.skip("testcontainers[opensearch] not installed")
    try:
        # OpenSearchContainer already sets:
        #   discovery.type=single-node, DISABLE_SECURITY_PLUGIN=true,
        #   OPENSEARCH_INITIAL_ADMIN_PASSWORD=admin (image >= 2.12)
        # Setting plugins.security.disabled here as well caused a duplicate-setting
        # error ("setting [plugins.security.disabled] already set"), making the
        # container exit with code 64 and the testcontainers wait to time out.
        container = OpenSearchContainer("opensearchproject/opensearch:2.13.0")
        container.start()
    except Exception as exc:  # noqa: BLE001 — Docker daemon down or image pull failure
        pytest.skip(f"opensearch container unavailable: {exc}")
    try:
        yield container
    finally:
        with contextlib.suppress(Exception):
            container.stop()


@pytest.fixture(scope="session")
def opensearch_client(opensearch_container: Any) -> Iterator[Any]:
    """Return an opensearch-py client bound to the test container.

    Builds the URL from the container's exposed host/port. The
    OpenSearchContainer convenience method ``get_client()`` exists, but it
    forces ``http_auth`` even when security is disabled, which is fine but
    unnecessary; an explicit URL keeps the client minimal.
    """
    from opensearchpy import OpenSearch

    host = opensearch_container.get_container_host_ip()
    port = opensearch_container.get_exposed_port(9200)
    url = f"http://{host}:{port}"
    client = OpenSearch([url], use_ssl=False, verify_certs=False)
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            client.close()
