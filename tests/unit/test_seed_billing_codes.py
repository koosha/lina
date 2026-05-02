"""Unit tests for the billing-code seed module."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.seed.billing_codes import BILLING_CODES, load_billing_codes

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


@pytest.mark.unit
def test_billing_codes_constant_has_three_categories() -> None:
    types = {c.code_type for c in BILLING_CODES}
    assert types == {"task", "activity", "expense"}


@pytest.mark.unit
def test_load_billing_codes_inserts_rows(applied: PgConnection) -> None:
    load_billing_codes(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_billing_code")
        count = cur.fetchone()[0]
    assert count == len(BILLING_CODES)


@pytest.mark.unit
def test_load_billing_codes_idempotent(applied: PgConnection) -> None:
    load_billing_codes(applied)
    load_billing_codes(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_billing_code")
        assert cur.fetchone()[0] == len(BILLING_CODES)


@pytest.mark.unit
def test_billing_codes_have_unique_ids() -> None:
    ids = [c.billing_code_id for c in BILLING_CODES]
    assert len(ids) == len(set(ids))
