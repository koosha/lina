"""line_item_detail — line-item-grain listing with mandatory filtering."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

from lina_redshift.templates.base import QueryTemplate, validate_template_sql
from lina_redshift.templates.invoice_search import DateRange

_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset(
    {
        "invoice_line_item_id",
        "invoice_id",
        "line_item_number",
        "matter_id",
        "client_matter_id",
        "vendor_id",
        "timekeeper_id",
        "line_item_date",
        "line_item_type",
        "task_code",
        "activity_code",
        "expense_code",
        "units",
        "unit_rate",
        "line_item_total_amount",
        "adjustment_amount",
        "approved_line_amount",
        "currency_code",
        "usd_amount",
        "review_status",
        "billing_guideline_flag",
        "billing_guideline_reason",
    }
)


class LineItemDetailParams(BaseModel):
    invoice_ids: list[str] | None = None
    matter_ids: list[str] | None = None
    task_codes: list[str] | None = None
    expense_codes: list[str] | None = None
    billing_guideline_flag: bool | None = None
    line_item_date_range: DateRange | None = None
    limit: int | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _at_least_one_filter(self) -> LineItemDetailParams:
        scoping = (
            self.invoice_ids,
            self.matter_ids,
            self.task_codes,
            self.expense_codes,
            self.line_item_date_range,
        )
        if not any(scoping):
            raise ValueError(
                "line_item_detail requires at least one scoping filter "
                "(invoice_ids, matter_ids, task_codes, expense_codes, "
                "or line_item_date_range)"
            )
        return self


class LineItemDetailTemplate(QueryTemplate):
    query_type: ClassVar[str] = "line_item_detail"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"legal_ops", "finance"})
    Params: ClassVar[type[BaseModel]] = LineItemDetailParams
    default_limit: ClassVar[int] = 500
    max_limit: ClassVar[int] = 5_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, LineItemDetailParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.invoice_ids:
            clauses.append("invoice_id = ANY(%(invoice_ids)s)")
            binds["invoice_ids"] = list(params.invoice_ids)
        if params.matter_ids:
            clauses.append("matter_id = ANY(%(matter_ids)s)")
            binds["matter_ids"] = list(params.matter_ids)
        if params.task_codes:
            clauses.append("task_code = ANY(%(task_codes)s)")
            binds["task_codes"] = list(params.task_codes)
        if params.expense_codes:
            clauses.append("expense_code = ANY(%(expense_codes)s)")
            binds["expense_codes"] = list(params.expense_codes)
        if params.billing_guideline_flag is not None:
            clauses.append("billing_guideline_flag = %(billing_guideline_flag)s")
            binds["billing_guideline_flag"] = params.billing_guideline_flag
        if params.line_item_date_range:
            clauses.append(
                "line_item_date BETWEEN %(line_item_date_start)s AND %(line_item_date_end)s"
            )
            binds["line_item_date_start"] = params.line_item_date_range.start
            binds["line_item_date_end"] = params.line_item_date_range.end

        where = " AND ".join(clauses)
        binds["limit"] = min(params.limit or self.default_limit, self.max_limit)
        sql = (
            "SELECT invoice_line_item_id, invoice_id, line_item_number, "
            "matter_id, client_matter_id, vendor_id, timekeeper_id, "
            "line_item_date, line_item_type, task_code, activity_code, expense_code, "
            "units, unit_rate, line_item_total_amount, adjustment_amount, "
            "approved_line_amount, currency_code, usd_amount, review_status, "
            "billing_guideline_flag, billing_guideline_reason "
            f"FROM fact_invoice_line_item WHERE {where} "
            "ORDER BY line_item_date DESC LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS} for row in rows]

    def validate_at_import(self) -> None:
        """Use a minimal valid params instance (one filter) to render SQL for AST checks."""
        sample = LineItemDetailParams(invoice_ids=["sample"])
        sql, _binds = self.build_sql(sample)
        validate_template_sql(sql)
