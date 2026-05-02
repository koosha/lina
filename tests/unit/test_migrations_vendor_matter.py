"""Verify vendor and matter dimension migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    runner = MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres")
    runner.apply_pending()
    return pg_conn


def _column_names(conn: PgConnection, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


@pytest.mark.unit
def test_dim_vendor_columns(applied: PgConnection) -> None:
    cols = _column_names(applied, "dim_vendor")
    expected = {
        "vendor_id", "vendor_name", "vendor_type", "vendor_status",
        "primary_contact_name", "primary_contact_email", "billing_contact_email",
        "country_code", "default_currency_code", "preferred_panel_flag",
        "created_at", "updated_at", "source_system",
    }
    assert expected <= cols


@pytest.mark.unit
def test_dim_matter_columns(applied: PgConnection) -> None:
    cols = _column_names(applied, "dim_matter")
    expected = {
        "matter_id", "client_matter_id", "matter_name", "matter_description",
        "matter_status", "matter_type", "practice_area", "open_date",
        "close_date", "matter_owner_user_id", "budget_amount", "budget_currency_code",
    }
    assert expected <= cols


@pytest.mark.unit
def test_dim_matter_accepts_unbounded_description(applied: PgConnection) -> None:
    """varchar(max) translates to plain varchar in Postgres — no length limit."""
    long_text = "x" * 100_000
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
            "matter_description, matter_status, matter_type, open_date, "
            "created_at, updated_at, source_system) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)",
            ("m_test", "CM-1", "Test", long_text, "open", "litigation", "2024-01-01", "test"),
        )
        cur.execute("SELECT length(matter_description) FROM dim_matter WHERE matter_id = %s",
                    ("m_test",))
        assert cur.fetchone()[0] == 100_000
