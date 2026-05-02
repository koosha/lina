"""Unit tests for line_item_detail template."""

from __future__ import annotations

from datetime import date

import pytest

from lina_redshift.templates.invoice_search import DateRange
from lina_redshift.templates.line_item_detail import (
    LineItemDetailParams,
    LineItemDetailTemplate,
)


@pytest.fixture
def template() -> LineItemDetailTemplate:
    return LineItemDetailTemplate()


@pytest.mark.unit
def test_build_sql_requires_at_least_one_filter(template: LineItemDetailTemplate) -> None:
    """Detail listings must always be scoped to avoid scanning the whole fact table."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="at least one"):
        LineItemDetailParams()


@pytest.mark.unit
def test_build_sql_filters_invoice_id(template: LineItemDetailTemplate) -> None:
    sql, binds = template.build_sql(LineItemDetailParams(invoice_ids=["inv1"]))
    assert "fact_invoice_line_item" in sql
    assert "invoice_id = ANY(%(invoice_ids)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_billing_guideline(template: LineItemDetailTemplate) -> None:
    params = LineItemDetailParams(
        invoice_ids=["inv1"],
        billing_guideline_flag=True,
    )
    sql, binds = template.build_sql(params)
    assert "billing_guideline_flag = %(billing_guideline_flag)s" in sql
    assert binds["billing_guideline_flag"] is True


@pytest.mark.unit
def test_build_sql_filters_date_range(template: LineItemDetailTemplate) -> None:
    params = LineItemDetailParams(
        matter_ids=["m1"],
        line_item_date_range=DateRange(start=date(2024, 1, 1), end=date(2024, 6, 30)),
    )
    sql, binds = template.build_sql(params)
    assert "line_item_date BETWEEN %(line_item_date_start)s AND %(line_item_date_end)s" in sql


@pytest.mark.unit
def test_allowed_roles(template: LineItemDetailTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance"})
