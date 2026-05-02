"""Verify budget and accrual fact migrations."""

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
def test_fact_matter_budget_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_matter_budget")
    expected = {
        "matter_budget_id",
        "matter_id",
        "budget_version",
        "budget_period_start_date",
        "budget_period_end_date",
        "budget_amount",
        "currency_code",
        "budget_status",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_matter_budget_supports_versions(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO fact_matter_budget (matter_budget_id, matter_id, "
            "budget_version, budget_period_start_date, budget_period_end_date, "
            "budget_amount, currency_code, budget_status, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
            "(%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            (
                "b1",
                "m1",
                1,
                "2024-01-01",
                "2024-12-31",
                100000,
                "USD",
                "approved",
                "b2",
                "m1",
                2,
                "2024-01-01",
                "2024-12-31",
                150000,
                "USD",
                "revised",
            ),
        )
        cur.execute("SELECT count(*) FROM fact_matter_budget WHERE matter_id = 'm1'")
        assert cur.fetchone()[0] == 2


@pytest.mark.unit
def test_fact_accrual_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_accrual")
    expected = {
        "accrual_id",
        "matter_id",
        "vendor_id",
        "accounting_period",
        "period_start_date",
        "period_end_date",
        "estimated_unbilled_amount",
        "currency_code",
        "accrual_status",
    }
    assert expected <= cols
