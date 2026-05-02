"""Verify view and materialized view migrations."""

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


@pytest.mark.unit
def test_vw_matter_current_exists(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.views WHERE table_name = 'vw_matter_current'"
        )
        assert cur.fetchone()[0] == 1


@pytest.mark.unit
def test_vw_matter_current_filters_archived(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
            "matter_status, matter_type, open_date, created_at, updated_at, source_system) "
            "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s), "
            "(%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)",
            (
                "m_open",
                "CM-1",
                "Open Matter",
                "open",
                "litigation",
                "2024-01-01",
                "test",
                "m_archived",
                "CM-2",
                "Archived",
                "archived",
                "advisory",
                "2020-01-01",
                "test",
            ),
        )
        applied.commit()
        cur.execute("SELECT matter_id FROM vw_matter_current ORDER BY matter_id")
        assert [r[0] for r in cur.fetchall()] == ["m_open"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "mv_name",
    ["mv_matter_spend_summary", "mv_vendor_spend_summary", "mv_timekeeper_rate_analysis"],
)
def test_materialized_view_exists(applied: PgConnection, mv_name: str) -> None:
    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM pg_matviews WHERE matviewname = %s", (mv_name,))
        assert cur.fetchone()[0] == 1


@pytest.mark.unit
def test_mv_matter_spend_summary_columns(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        # Postgres excludes materialized views from information_schema.columns,
        # so introspect via pg_attribute / pg_class instead.
        cur.execute(
            "SELECT a.attname FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid "
            "WHERE c.relname = 'mv_matter_spend_summary' AND a.attnum > 0 "
            "AND NOT a.attisdropped"
        )
        cols = {r[0] for r in cur.fetchall()}
    expected = {
        "matter_id",
        "fiscal_period",
        "total_billed_amount",
        "total_approved_amount",
        "total_paid_amount",
        "fee_amount",
        "expense_amount",
        "tax_amount",
        "adjustment_amount",
        "invoice_count",
        "vendor_count",
        "timekeeper_count",
        "budget_amount",
        "budget_remaining",
        "budget_utilization_percent",
    }
    assert expected <= cols
