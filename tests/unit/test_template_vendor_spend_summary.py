"""Unit tests for vendor_spend_summary template."""

from __future__ import annotations

import pytest

from lina_redshift.templates.vendor_spend_summary import (
    VendorSpendSummaryParams,
    VendorSpendSummaryTemplate,
)


@pytest.fixture
def template() -> VendorSpendSummaryTemplate:
    return VendorSpendSummaryTemplate()


@pytest.mark.unit
def test_params_default_metrics() -> None:
    p = VendorSpendSummaryParams()
    assert "total_approved_amount" in p.metrics
    assert "billing_guideline_flag_count" in p.metrics


@pytest.mark.unit
def test_build_sql_filters_vendor_ids(template: VendorSpendSummaryTemplate) -> None:
    sql, binds = template.build_sql(VendorSpendSummaryParams(vendor_ids=["v1", "v2"]))
    assert "mv_vendor_spend_summary" in sql
    assert "vendor_id = ANY(%(vendor_ids)s)" in sql
    assert binds["vendor_ids"] == ["v1", "v2"]


@pytest.mark.unit
def test_build_sql_filters_fiscal_period(template: VendorSpendSummaryTemplate) -> None:
    sql, binds = template.build_sql(VendorSpendSummaryParams(fiscal_periods=["2024-Q1"]))
    assert "fiscal_period = ANY(%(fiscal_periods)s)" in sql


@pytest.mark.unit
def test_shape_packet_strips_unknown_columns(template: VendorSpendSummaryTemplate) -> None:
    rows = [{"vendor_id": "v1", "total_billed_amount": 100, "leak": "x"}]
    out = template.shape_packet(rows)
    assert "leak" not in out[0]


@pytest.mark.unit
def test_allowed_roles(template: VendorSpendSummaryTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance"})
