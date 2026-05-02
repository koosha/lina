"""Unit tests for named-entity seed."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.seed.named_entities import (
    NAMED_INVOICES,
    NAMED_LINE_ITEMS,
    NAMED_MATTERS,
    NAMED_TIMEKEEPERS,
    NAMED_VENDORS,
    load_named_entities,
)

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


@pytest.mark.unit
def test_named_matters_have_recognizable_ids() -> None:
    ids = {m.matter_id for m in NAMED_MATTERS}
    assert "matter_acme_v_beta" in ids
    assert "matter_acme_privacy_review" in ids
    assert "matter_acme_employment_2023" in ids


@pytest.mark.unit
def test_named_vendors_recognizable() -> None:
    ids = {v.vendor_id for v in NAMED_VENDORS}
    assert ids >= {"vendor_walker", "vendor_jones", "vendor_meridian"}


@pytest.mark.unit
def test_load_named_entities_inserts_all(applied: PgConnection) -> None:
    load_named_entities(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        assert cur.fetchone()[0] == len(NAMED_MATTERS)
        cur.execute("SELECT count(*) FROM dim_vendor")
        assert cur.fetchone()[0] == len(NAMED_VENDORS)
        cur.execute("SELECT count(*) FROM dim_timekeeper")
        assert cur.fetchone()[0] == len(NAMED_TIMEKEEPERS)
        cur.execute("SELECT count(*) FROM fact_invoice")
        assert cur.fetchone()[0] == len(NAMED_INVOICES)
        cur.execute("SELECT count(*) FROM fact_invoice_line_item")
        assert cur.fetchone()[0] == len(NAMED_LINE_ITEMS)


@pytest.mark.unit
def test_named_ids_are_unique() -> None:
    matter_ids = [m.matter_id for m in NAMED_MATTERS]
    assert len(matter_ids) == len(set(matter_ids))
    vendor_ids = [v.vendor_id for v in NAMED_VENDORS]
    assert len(vendor_ids) == len(set(vendor_ids))
    tk_ids = [t.timekeeper_id for t in NAMED_TIMEKEEPERS]
    assert len(tk_ids) == len(set(tk_ids))


@pytest.mark.unit
def test_load_named_entities_idempotent(applied: PgConnection) -> None:
    load_named_entities(applied)
    load_named_entities(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        assert cur.fetchone()[0] == len(NAMED_MATTERS)
