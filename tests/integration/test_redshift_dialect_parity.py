"""Verify each migration applies cleanly to real Redshift Serverless.

These tests assume a fresh namespace; they do not clean up after themselves.
Run against a workgroup dedicated to test/CI use.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.mark.integration
def test_apply_pending_against_redshift(redshift_conn: PgConnection) -> None:
    runner = MigrationRunner(connection=redshift_conn, sql_dir=SQL_DIR, target="redshift")
    runner.apply_pending()  # idempotent; safe to re-run


@pytest.mark.integration
def test_all_18_migrations_recorded_after_apply(redshift_conn: PgConnection) -> None:
    runner = MigrationRunner(connection=redshift_conn, sql_dir=SQL_DIR, target="redshift")
    runner.apply_pending()

    with redshift_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM schema_migrations")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 18


@pytest.mark.integration
def test_each_table_exists_in_redshift(redshift_conn: PgConnection) -> None:
    expected = [
        "dim_legal_entity",
        "dim_cost_center",
        "dim_billing_code",
        "dim_vendor",
        "dim_matter",
        "dim_timekeeper",
        "fact_timekeeper_rate",
        "fact_invoice",
        "fact_invoice_line_item",
        "fact_matter_budget",
        "fact_accrual",
        "bridge_matter_vendor",
        "bridge_matter_person",
        "bridge_matter_allocation",
    ]
    with redshift_conn.cursor() as cur:
        for table in expected:
            cur.execute(
                "SELECT count(*) FROM pg_table_def WHERE tablename = %s", (table,)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] > 0, f"table {table} not present in Redshift"


@pytest.mark.integration
def test_views_and_mvs_exist_in_redshift(redshift_conn: PgConnection) -> None:
    with redshift_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.views WHERE table_name = 'vw_matter_current'"
        )
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1
        for mv in [
            "mv_matter_spend_summary",
            "mv_vendor_spend_summary",
            "mv_timekeeper_rate_analysis",
        ]:
            cur.execute(
                "SELECT count(*) FROM stv_mv_info WHERE name = %s", (mv,)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == 1, f"materialized view {mv} not present"
