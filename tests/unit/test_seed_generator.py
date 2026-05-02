"""Unit tests for the deterministic Faker bulk generator."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.seed.generator import (
    GeneratedSeed,
    generate_seed,
    load_bulk_generated,
)
from lina_redshift.seed.named_entities import load_named_entities

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    load_named_entities(pg_conn)
    return pg_conn


@pytest.mark.unit
def test_generator_is_deterministic() -> None:
    a: GeneratedSeed = generate_seed()
    b: GeneratedSeed = generate_seed()
    assert [m.matter_id for m in a.matters] == [m.matter_id for m in b.matters]
    assert [li.invoice_line_item_id for li in a.line_items] == [
        li.invoice_line_item_id for li in b.line_items
    ]


@pytest.mark.unit
def test_generator_volumes_match_spec() -> None:
    seed = generate_seed()
    assert len(seed.matters) == 100
    assert len(seed.vendors) == 25
    assert len(seed.timekeepers) == 200
    assert len(seed.invoices) == 600
    assert 5_500 <= len(seed.line_items) <= 6_500


@pytest.mark.unit
def test_generated_ids_disjoint_from_named() -> None:
    """Generated IDs must not collide with hand-written named entity IDs."""
    seed = generate_seed()
    matter_ids = {m.matter_id for m in seed.matters}
    assert "matter_acme_v_beta" not in matter_ids
    vendor_ids = {v.vendor_id for v in seed.vendors}
    assert "vendor_walker" not in vendor_ids


@pytest.mark.unit
def test_generated_currency_distribution() -> None:
    """80% USD, 10% GBP, 5% EUR, 5% other."""
    seed = generate_seed()
    currencies = [inv.currency_code for inv in seed.invoices]
    usd = sum(1 for c in currencies if c == "USD")
    assert 0.70 < usd / len(currencies) < 0.90


@pytest.mark.unit
def test_generated_line_items_some_billing_flagged() -> None:
    seed = generate_seed()
    flagged = sum(1 for li in seed.line_items if li.billing_guideline_flag)
    assert flagged > 0


@pytest.mark.unit
def test_load_bulk_generated_inserts_rows(applied: PgConnection) -> None:
    load_bulk_generated(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        assert cur.fetchone()[0] >= 100  # named + generated
        cur.execute("SELECT count(*) FROM fact_invoice")
        assert cur.fetchone()[0] >= 600
        cur.execute("SELECT count(*) FROM fact_invoice_line_item")
        assert cur.fetchone()[0] >= 5_500
