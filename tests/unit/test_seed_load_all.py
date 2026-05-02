"""Verify load_all populates everything and refreshes MVs."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.seed import load_all

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


@pytest.mark.unit
def test_load_all_populates_everything(applied: PgConnection) -> None:
    load_all(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_billing_code")
        assert cur.fetchone()[0] >= 50  # ~50 utbms codes
        cur.execute("SELECT count(*) FROM dim_matter")
        assert cur.fetchone()[0] >= 100
        cur.execute("SELECT count(*) FROM fact_invoice_line_item")
        assert cur.fetchone()[0] >= 5_500


@pytest.mark.unit
def test_load_all_refreshes_materialized_views(applied: PgConnection) -> None:
    load_all(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM mv_matter_spend_summary")
        msc = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM mv_vendor_spend_summary")
        vsc = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM mv_timekeeper_rate_analysis")
        tra = cur.fetchone()[0]
    assert msc > 0
    assert vsc > 0
    assert tra > 0


@pytest.mark.unit
def test_load_all_with_reset_truncates_first(applied: PgConnection) -> None:
    load_all(applied)
    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        first_count = cur.fetchone()[0]

    load_all(applied, reset=True)
    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        second_count = cur.fetchone()[0]

    assert first_count == second_count  # deterministic seed -> same count after reset
