"""matter_spend_summary template — fast matter-level spend metrics."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from lina_redshift.templates.base import QueryTemplate

MetricName = Literal[
    "total_billed_amount",
    "total_approved_amount",
    "total_paid_amount",
    "fee_amount",
    "expense_amount",
    "tax_amount",
    "adjustment_amount",
    "invoice_count",
    "vendor_count",
    "timekeeper_count",
    "budget_amount",
    "budget_remaining",
    "budget_utilization_percent",
]

_ALL_METRICS: list[MetricName] = list(MetricName.__args__)  # type: ignore[attr-defined]
_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({"matter_id", "fiscal_period", *_ALL_METRICS})


class MatterSpendSummaryParams(BaseModel):
    matter_ids: list[str] | None = None
    fiscal_periods: list[str] | None = None
    metrics: list[MetricName] = Field(default_factory=lambda: list(_ALL_METRICS))
    limit: int | None = None

    model_config = {"frozen": True}


class MatterSpendSummaryTemplate(QueryTemplate):
    query_type: ClassVar[str] = "matter_spend_summary"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"legal_ops", "finance", "matter_owner"})
    Params: ClassVar[type[BaseModel]] = MatterSpendSummaryParams
    default_limit: ClassVar[int] = 500
    max_limit: ClassVar[int] = 5_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, MatterSpendSummaryParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.matter_ids:
            clauses.append("matter_id = ANY(%(matter_ids)s)")
            binds["matter_ids"] = list(params.matter_ids)
        if params.fiscal_periods:
            clauses.append("fiscal_period = ANY(%(fiscal_periods)s)")
            binds["fiscal_periods"] = list(params.fiscal_periods)

        where = " AND ".join(clauses) if clauses else "1=1"
        effective_limit = min(params.limit or self.default_limit, self.max_limit)
        binds["limit"] = effective_limit

        select_cols = ["matter_id", "fiscal_period", *params.metrics]
        sql = (
            f"SELECT {', '.join(select_cols)} FROM mv_matter_spend_summary "
            f"WHERE {where} LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS} for row in rows]
