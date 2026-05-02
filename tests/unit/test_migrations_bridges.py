"""Verify bridge table migrations."""

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
def test_bridge_matter_vendor_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "bridge_matter_vendor")
    assert {"matter_id", "vendor_id", "vendor_role", "active_flag"} <= cols


@pytest.mark.unit
def test_bridge_matter_vendor_composite_key(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO bridge_matter_vendor (matter_id, vendor_id, vendor_role, active_flag) "
            "VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)",
            ("m1", "v1", "primary_counsel", True,
             "m1", "v1", "local_counsel", True),
        )
        cur.execute(
            "SELECT count(*) FROM bridge_matter_vendor "
            "WHERE matter_id='m1' AND vendor_id='v1'"
        )
        assert cur.fetchone()[0] == 2


@pytest.mark.unit
def test_bridge_matter_person_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "bridge_matter_person")
    assert {"matter_id", "person_id", "person_source", "person_role", "active_flag"} <= cols


@pytest.mark.unit
def test_bridge_matter_allocation_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "bridge_matter_allocation")
    expected = {
        "matter_id", "legal_entity_id", "cost_center_id", "gl_account",
        "allocation_percentage", "effective_start_date", "effective_end_date",
        "active_flag",
    }
    assert expected <= cols


@pytest.mark.unit
def test_bridge_matter_allocation_decimal_precision(applied: PgConnection) -> None:
    """allocation_percentage is decimal(9,6) — 99.999999% upper bound."""
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO bridge_matter_allocation (matter_id, legal_entity_id, "
            "cost_center_id, gl_account, allocation_percentage, "
            "effective_start_date, active_flag) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s)",
            ("m1", "le_us", "cc_eng", "GL-1234", "0.333333", "2024-01-01", True),
        )
        cur.execute(
            "SELECT allocation_percentage FROM bridge_matter_allocation "
            "WHERE matter_id='m1'"
        )
        assert str(cur.fetchone()[0]) == "0.333333"
