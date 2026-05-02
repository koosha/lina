"""End-to-end unit tests for RedshiftWorker against Postgres."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.caller import CallerContext
from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.packet import ErrorPacket, ResultPacket
from lina_redshift.worker import RedshiftWorker

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def worker_db(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
            "matter_status, matter_type, open_date, created_at, updated_at, source_system) "
            "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)",
            ("matter_acme", "CM-1", "Acme v. Beta", "open", "litigation", "2024-06-01", "test"),
        )
    pg_conn.commit()
    return pg_conn


@pytest.fixture
def legal_ops_caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane",
        roles=frozenset({"legal_ops"}),
        request_id="req_1",
    )


@pytest.fixture
def matter_owner_caller() -> CallerContext:
    return CallerContext(
        user_id="user_alex",
        roles=frozenset({"matter_owner"}),
        request_id="req_2",
    )


@pytest.fixture
def unauthorized_caller() -> CallerContext:
    return CallerContext(
        user_id="user_bob",
        roles=frozenset({"random_role"}),
        request_id="req_3",
    )


@pytest.fixture
def worker(worker_db: PgConnection) -> RedshiftWorker:
    return RedshiftWorker(connection=worker_db)


@pytest.mark.unit
def test_run_returns_result_packet(worker: RedshiftWorker, legal_ops_caller: CallerContext) -> None:
    packet = worker.run(
        query_type="matter_lookup",
        params={"matter_id": "matter_acme"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 1
    assert packet.metrics[0]["matter_id"] == "matter_acme"
    assert packet.metrics[0]["matter_name"] == "Acme v. Beta"
    assert packet.sql_trace_id


@pytest.mark.unit
def test_run_unknown_template_returns_error_packet(
    worker: RedshiftWorker,
    legal_ops_caller: CallerContext,
) -> None:
    packet = worker.run(
        query_type="bogus",
        params={},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ErrorPacket)
    assert packet.error.type == "UnknownTemplateError"


@pytest.mark.unit
def test_run_missing_role_returns_error_packet(
    worker: RedshiftWorker,
    unauthorized_caller: CallerContext,
) -> None:
    packet = worker.run(
        query_type="matter_spend_summary",
        params={},
        caller=unauthorized_caller,
    )
    assert isinstance(packet, ErrorPacket)
    assert packet.error.type == "AuthorizationError"


@pytest.mark.unit
def test_run_invalid_params_returns_error_packet(
    worker: RedshiftWorker,
    legal_ops_caller: CallerContext,
) -> None:
    packet = worker.run(
        query_type="matter_lookup",
        params={},  # no lookup field
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ErrorPacket)
    assert packet.error.type == "InvalidParametersError"


@pytest.mark.unit
def test_run_attaches_truncated_when_max_limit_hit(
    worker_db: PgConnection,
    legal_ops_caller: CallerContext,
) -> None:
    """Insert enough rows to hit max_limit and verify truncated=True."""
    with worker_db.cursor() as cur:
        for i in range(1, 6):
            cur.execute(
                "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
                "matter_status, matter_type, open_date, matter_owner_user_id, "
                "created_at, updated_at, source_system) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)",
                (
                    f"m_{i}",
                    f"CM-{i}",
                    f"Owned Matter {i}",
                    "open",
                    "litigation",
                    "2024-01-01",
                    "user_jane",
                    "test",
                ),
            )
    worker_db.commit()
    worker = RedshiftWorker(connection=worker_db)
    packet = worker.run(
        query_type="matter_lookup",
        params={"matter_owner_user_id": "user_jane", "limit": 2},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 2
    assert packet.truncated is True


@pytest.mark.unit
def test_run_returns_empty_metrics_for_no_match(
    worker: RedshiftWorker,
    legal_ops_caller: CallerContext,
) -> None:
    packet = worker.run(
        query_type="matter_lookup",
        params={"matter_id": "no_such_matter"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 0
    assert packet.metrics == []
