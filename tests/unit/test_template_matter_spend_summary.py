"""Unit tests for matter_spend_summary template."""

from __future__ import annotations

import pytest

from lina_redshift.templates.matter_spend_summary import (
    MatterSpendSummaryParams,
    MatterSpendSummaryTemplate,
)


@pytest.fixture
def template() -> MatterSpendSummaryTemplate:
    return MatterSpendSummaryTemplate()


@pytest.mark.unit
def test_params_default_metric_set() -> None:
    p = MatterSpendSummaryParams()
    assert "total_approved_amount" in p.metrics


@pytest.mark.unit
def test_params_rejects_unknown_metric() -> None:
    with pytest.raises(Exception):  # pydantic ValidationError on Literal
        MatterSpendSummaryParams(metrics=["bogus_metric"])  # type: ignore[list-item]


@pytest.mark.unit
def test_build_sql_no_filters(template: MatterSpendSummaryTemplate) -> None:
    sql, binds = template.build_sql(MatterSpendSummaryParams())
    assert "mv_matter_spend_summary" in sql
    assert "WHERE" not in sql.upper().split("LIMIT")[0] or "WHERE 1=1" in sql
    assert binds["limit"] == template.default_limit


@pytest.mark.unit
def test_build_sql_filters_matter_ids(template: MatterSpendSummaryTemplate) -> None:
    params = MatterSpendSummaryParams(matter_ids=["m1", "m2"])
    sql, binds = template.build_sql(params)
    assert "matter_id = ANY(%(matter_ids)s)" in sql
    assert binds["matter_ids"] == ["m1", "m2"]


@pytest.mark.unit
def test_build_sql_filters_fiscal_period(template: MatterSpendSummaryTemplate) -> None:
    params = MatterSpendSummaryParams(fiscal_periods=["2024-Q1", "2024-Q2"])
    sql, binds = template.build_sql(params)
    assert "fiscal_period = ANY(%(fiscal_periods)s)" in sql
    assert binds["fiscal_periods"] == ["2024-Q1", "2024-Q2"]


@pytest.mark.unit
def test_limit_clamped_to_max(template: MatterSpendSummaryTemplate) -> None:
    params = MatterSpendSummaryParams(limit=999_999)
    _sql, binds = template.build_sql(params)
    assert binds["limit"] == template.max_limit


@pytest.mark.unit
def test_shape_packet_projects_metrics(template: MatterSpendSummaryTemplate) -> None:
    rows = [
        {"matter_id": "m1", "fiscal_period": "2024-Q1",
         "total_approved_amount": 1000, "internal_only": "leak"},
    ]
    out = template.shape_packet(rows)
    assert out[0]["matter_id"] == "m1"
    assert "internal_only" not in out[0]


@pytest.mark.unit
def test_allowed_roles(template: MatterSpendSummaryTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance", "matter_owner"})
