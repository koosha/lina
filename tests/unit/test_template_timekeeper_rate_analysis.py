"""Unit tests for timekeeper_rate_analysis template."""

from __future__ import annotations

import pytest

from lina_redshift.templates.timekeeper_rate_analysis import (
    TimekeeperRateAnalysisParams,
    TimekeeperRateAnalysisTemplate,
)


@pytest.fixture
def template() -> TimekeeperRateAnalysisTemplate:
    return TimekeeperRateAnalysisTemplate()


@pytest.mark.unit
def test_params_default_threshold_is_none() -> None:
    p = TimekeeperRateAnalysisParams()
    assert p.rate_variance_threshold is None


@pytest.mark.unit
def test_build_sql_filters_vendor_ids(template: TimekeeperRateAnalysisTemplate) -> None:
    sql, binds = template.build_sql(TimekeeperRateAnalysisParams(vendor_ids=["v1"]))
    assert "mv_timekeeper_rate_analysis" in sql
    assert "vendor_id = ANY(%(vendor_ids)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_timekeeper_ids(template: TimekeeperRateAnalysisTemplate) -> None:
    sql, binds = template.build_sql(TimekeeperRateAnalysisParams(timekeeper_ids=["tk1"]))
    assert "timekeeper_id = ANY(%(timekeeper_ids)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_variance_threshold(template: TimekeeperRateAnalysisTemplate) -> None:
    sql, binds = template.build_sql(
        TimekeeperRateAnalysisParams(rate_variance_threshold=0.1)
    )
    assert "abs(rate_variance_percent) >= %(rate_variance_threshold)s" in sql
    assert binds["rate_variance_threshold"] == 0.1


@pytest.mark.unit
def test_allowed_roles(template: TimekeeperRateAnalysisTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance", "rate_admin"})
