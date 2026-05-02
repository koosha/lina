"""Unit tests for invoice_search template."""

from __future__ import annotations

from datetime import date

import pytest

from lina_redshift.templates.invoice_search import (
    DateRange,
    InvoiceSearchParams,
    InvoiceSearchTemplate,
)


@pytest.fixture
def template() -> InvoiceSearchTemplate:
    return InvoiceSearchTemplate()


@pytest.mark.unit
def test_build_sql_filters_matter_ids(template: InvoiceSearchTemplate) -> None:
    sql, binds = template.build_sql(InvoiceSearchParams(matter_ids=["m1"]))
    assert "fact_invoice" in sql
    assert "matter_id = ANY(%(matter_ids)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_invoice_status(template: InvoiceSearchTemplate) -> None:
    sql, binds = template.build_sql(InvoiceSearchParams(invoice_status=["paid"]))
    assert "invoice_status = ANY(%(invoice_status)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_date_range(template: InvoiceSearchTemplate) -> None:
    params = InvoiceSearchParams(
        invoice_date_range=DateRange(start=date(2024, 1, 1), end=date(2024, 12, 31)),
    )
    sql, binds = template.build_sql(params)
    assert "invoice_date BETWEEN %(invoice_date_start)s AND %(invoice_date_end)s" in sql
    assert binds["invoice_date_start"] == date(2024, 1, 1)
    assert binds["invoice_date_end"] == date(2024, 12, 31)


@pytest.mark.unit
def test_build_sql_filters_amount_range(template: InvoiceSearchTemplate) -> None:
    sql, binds = template.build_sql(
        InvoiceSearchParams(min_amount=1000, max_amount=50000)
    )
    assert "invoice_total_amount >= %(min_amount)s" in sql
    assert "invoice_total_amount <= %(max_amount)s" in sql


@pytest.mark.unit
def test_allowed_roles(template: InvoiceSearchTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance", "matter_owner"})


@pytest.mark.unit
def test_shape_packet_strips_unknown(template: InvoiceSearchTemplate) -> None:
    rows = [{"invoice_id": "inv1", "invoice_total_amount": 100, "secret": "leak"}]
    out = template.shape_packet(rows)
    assert "secret" not in out[0]
