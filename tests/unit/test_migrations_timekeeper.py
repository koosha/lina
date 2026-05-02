"""Verify timekeeper dimension and rate fact migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


def _columns(conn: PgConnection, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


@pytest.mark.unit
def test_dim_timekeeper_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "dim_timekeeper")
    expected = {
        "timekeeper_id", "vendor_id", "timekeeper_name", "timekeeper_email",
        "timekeeper_classification", "years_of_experience", "active_status",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_timekeeper_rate_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_timekeeper_rate")
    expected = {
        "rate_id", "timekeeper_id", "vendor_id", "matter_id", "rate_type",
        "hourly_rate", "currency_code", "effective_start_date",
        "effective_end_date", "approval_status",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_timekeeper_rate_supports_history(applied: PgConnection) -> None:
    """Two rates for the same timekeeper with non-overlapping effective ranges."""
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO fact_timekeeper_rate (rate_id, timekeeper_id, vendor_id, "
            "rate_type, hourly_rate, currency_code, effective_start_date, "
            "effective_end_date, approval_status, created_at) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP), "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
            ("r1", "tk1", "v1", "standard", 600, "USD", "2023-01-01",
             "2023-12-31", "approved",
             "r2", "tk1", "v1", "standard", 650, "USD", "2024-01-01",
             None, "approved"),
        )
        cur.execute(
            "SELECT count(*) FROM fact_timekeeper_rate WHERE timekeeper_id = 'tk1'"
        )
        assert cur.fetchone()[0] == 2
