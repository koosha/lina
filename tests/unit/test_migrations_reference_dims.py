"""Verify reference dimension migrations create expected tables."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


def _columns(conn: PgConnection, table: str) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position",
            (table,),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    runner = MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres")
    runner.apply_pending()
    return pg_conn


@pytest.mark.unit
def test_dim_legal_entity_exists(applied: PgConnection) -> None:
    cols = dict(_columns(applied, "dim_legal_entity"))
    assert cols["legal_entity_id"] == "character varying"
    assert cols["legal_entity_name"] == "character varying"
    assert cols["entity_status"] == "character varying"
    assert cols["created_at"] == "timestamp without time zone"


@pytest.mark.unit
def test_dim_cost_center_exists(applied: PgConnection) -> None:
    cols = dict(_columns(applied, "dim_cost_center"))
    assert "cost_center_id" in cols
    assert "cost_center_name" in cols
    assert "active_status" in cols


@pytest.mark.unit
def test_dim_billing_code_exists(applied: PgConnection) -> None:
    cols = dict(_columns(applied, "dim_billing_code"))
    assert "billing_code_id" in cols
    assert cols["code_type"] == "character varying"
    assert cols["code_set"] == "character varying"
