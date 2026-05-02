"""Seed loaders for the legal_matter_spend schema."""

from __future__ import annotations

from psycopg2.extensions import connection as PgConnection  # noqa: N812


def load_all(connection: PgConnection, *, reset: bool = False) -> None:
    """Load all seed data layers in dependency order."""
    from lina_redshift.seed.billing_codes import load_billing_codes
    from lina_redshift.seed.generator import load_bulk_generated
    from lina_redshift.seed.named_entities import load_named_entities

    if reset:
        _truncate_all(connection)

    load_billing_codes(connection)
    load_named_entities(connection)
    load_bulk_generated(connection)
    _refresh_materialized_views(connection)


_TRUNCATE_ORDER: list[str] = [
    "fact_invoice_line_item",
    "fact_invoice",
    "fact_timekeeper_rate",
    "fact_matter_budget",
    "fact_accrual",
    "bridge_matter_vendor",
    "bridge_matter_person",
    "bridge_matter_allocation",
    "dim_timekeeper",
    "dim_matter",
    "dim_vendor",
    "dim_billing_code",
    "dim_cost_center",
    "dim_legal_entity",
]

_MATERIALIZED_VIEWS: list[str] = [
    "mv_matter_spend_summary",
    "mv_vendor_spend_summary",
    "mv_timekeeper_rate_analysis",
]


def _truncate_all(connection: PgConnection) -> None:
    with connection.cursor() as cur:
        for table in _TRUNCATE_ORDER:
            cur.execute(f"TRUNCATE {table} CASCADE")
    connection.commit()


def _refresh_materialized_views(connection: PgConnection) -> None:
    """Refresh MVs (Postgres requires explicit refresh; Redshift handles via AUTO REFRESH)."""
    with connection.cursor() as cur:
        for mv in _MATERIALIZED_VIEWS:
            cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
    connection.commit()
