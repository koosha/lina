"""timekeeper_rate_analysis — rate comparison and rate enforcement."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from lina_redshift.templates.base import QueryTemplate

_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({
    "timekeeper_id", "vendor_id", "fiscal_period",
    "billed_hours", "billed_amount", "average_billed_rate",
    "approved_rate", "rate_variance_amount", "rate_variance_percent",
})


class TimekeeperRateAnalysisParams(BaseModel):
    vendor_ids: list[str] | None = None
    timekeeper_ids: list[str] | None = None
    fiscal_periods: list[str] | None = None
    rate_variance_threshold: float | None = None
    limit: int | None = None

    model_config = {"frozen": True}


class TimekeeperRateAnalysisTemplate(QueryTemplate):
    query_type: ClassVar[str] = "timekeeper_rate_analysis"
    allowed_roles: ClassVar[frozenset[str]] = frozenset(
        {"legal_ops", "finance", "rate_admin"}
    )
    Params: ClassVar[type[BaseModel]] = TimekeeperRateAnalysisParams
    default_limit: ClassVar[int] = 500
    max_limit: ClassVar[int] = 5_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, TimekeeperRateAnalysisParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.vendor_ids:
            clauses.append("vendor_id = ANY(%(vendor_ids)s)")
            binds["vendor_ids"] = list(params.vendor_ids)
        if params.timekeeper_ids:
            clauses.append("timekeeper_id = ANY(%(timekeeper_ids)s)")
            binds["timekeeper_ids"] = list(params.timekeeper_ids)
        if params.fiscal_periods:
            clauses.append("fiscal_period = ANY(%(fiscal_periods)s)")
            binds["fiscal_periods"] = list(params.fiscal_periods)
        if params.rate_variance_threshold is not None:
            clauses.append("abs(rate_variance_percent) >= %(rate_variance_threshold)s")
            binds["rate_variance_threshold"] = params.rate_variance_threshold

        where = " AND ".join(clauses) if clauses else "1=1"
        binds["limit"] = min(params.limit or self.default_limit, self.max_limit)
        sql = (
            "SELECT timekeeper_id, vendor_id, fiscal_period, billed_hours, "
            "billed_amount, average_billed_rate, approved_rate, "
            "rate_variance_amount, rate_variance_percent "
            f"FROM mv_timekeeper_rate_analysis WHERE {where} LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
