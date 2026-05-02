"""Verify invoice and line item fact migrations."""

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
def test_fact_invoice_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_invoice")
    expected = {
        "invoice_id",
        "invoice_number",
        "matter_id",
        "vendor_id",
        "invoice_date",
        "invoice_status",
        "currency_code",
        "invoice_total_amount",
        "fee_total_amount",
        "expense_total_amount",
        "approved_amount",
        "paid_amount",
        "ledes_format",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_invoice_line_item_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_invoice_line_item")
    expected = {
        "invoice_line_item_id",
        "invoice_id",
        "line_item_number",
        "matter_id",
        "vendor_id",
        "timekeeper_id",
        "line_item_date",
        "line_item_type",
        "task_code",
        "activity_code",
        "expense_code",
        "units",
        "unit_rate",
        "line_item_total_amount",
        "adjustment_amount",
        "approved_line_amount",
        "currency_code",
        "usd_amount",
        "fx_rate_to_usd",
        "billing_guideline_flag",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_invoice_line_item_decimal_precision(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO fact_invoice_line_item (invoice_line_item_id, invoice_id, "
            "line_item_number, matter_id, client_matter_id, vendor_id, "
            "line_item_date, line_item_type, line_item_total_amount, currency_code, "
            "fx_rate_to_usd, created_at) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
            (
                "li1",
                "inv1",
                1,
                "m1",
                "CM-1",
                "v1",
                "2024-06-15",
                "fee",
                "1234.56",
                "USD",
                "1.23456789",
            ),
        )
        cur.execute(
            "SELECT line_item_total_amount, fx_rate_to_usd FROM fact_invoice_line_item "
            "WHERE invoice_line_item_id = 'li1'"
        )
        amount, fx = cur.fetchone()
        assert str(amount) == "1234.56"
        assert str(fx) == "1.23456789"
