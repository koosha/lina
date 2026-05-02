"""vendor_spend_summary template — vendor comparison and outside counsel analytics."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from lina_redshift.templates.base import QueryTemplate

MetricName = Literal[
    "total_billed_amount", "total_approved_amount",
    "matter_count", "invoice_count",
    "average_hourly_rate", "partner_hours", "associate_hours",
    "expense_amount", "adjustment_amount", "billing_guideline_flag_count",
]

_ALL_METRICS: list[MetricName] = list(MetricName.__args__)  # type: ignore[attr-defined]
_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({"vendor_id", "fiscal_period", *_ALL_METRICS})


class VendorSpendSummaryParams(BaseModel):
    vendor_ids: list[str] | None = None
    fiscal_periods: list[str] | None = None
    metrics: list[MetricName] = Field(default_factory=lambda: list(_ALL_METRICS))
    limit: int | None = None

    model_config = {"frozen": True}


class VendorSpendSummaryTemplate(QueryTemplate):
    query_type: ClassVar[str] = "vendor_spend_summary"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"legal_ops", "finance"})
    Params: ClassVar[type[BaseModel]] = VendorSpendSummaryParams
    default_limit: ClassVar[int] = 500
    max_limit: ClassVar[int] = 5_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, VendorSpendSummaryParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.vendor_ids:
            clauses.append("vendor_id = ANY(%(vendor_ids)s)")
            binds["vendor_ids"] = list(params.vendor_ids)
        if params.fiscal_periods:
            clauses.append("fiscal_period = ANY(%(fiscal_periods)s)")
            binds["fiscal_periods"] = list(params.fiscal_periods)

        where = " AND ".join(clauses) if clauses else "1=1"
        binds["limit"] = min(params.limit or self.default_limit, self.max_limit)
        select_cols = ["vendor_id", "fiscal_period", *params.metrics]
        sql = (
            f"SELECT {', '.join(select_cols)} FROM mv_vendor_spend_summary "
            f"WHERE {where} LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
