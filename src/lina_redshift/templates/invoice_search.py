"""invoice_search — filtered listing of fact_invoice rows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, ClassVar

from pydantic import BaseModel

from lina_redshift.templates.base import QueryTemplate

_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({
    "invoice_id", "invoice_number", "matter_id", "client_matter_id",
    "vendor_id", "invoice_date", "billing_start_date", "billing_end_date",
    "invoice_status", "approval_status", "currency_code",
    "invoice_total_amount", "fee_total_amount", "expense_total_amount",
    "approved_amount", "paid_amount", "payment_date",
})


class DateRange(BaseModel):
    start: date
    end: date

    model_config = {"frozen": True}


class InvoiceSearchParams(BaseModel):
    matter_ids: list[str] | None = None
    vendor_ids: list[str] | None = None
    invoice_status: list[str] | None = None
    invoice_date_range: DateRange | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    limit: int | None = None

    model_config = {"frozen": True}


class InvoiceSearchTemplate(QueryTemplate):
    query_type: ClassVar[str] = "invoice_search"
    allowed_roles: ClassVar[frozenset[str]] = frozenset(
        {"legal_ops", "finance", "matter_owner"}
    )
    Params: ClassVar[type[BaseModel]] = InvoiceSearchParams
    default_limit: ClassVar[int] = 200
    max_limit: ClassVar[int] = 2_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, InvoiceSearchParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.matter_ids:
            clauses.append("matter_id = ANY(%(matter_ids)s)")
            binds["matter_ids"] = list(params.matter_ids)
        if params.vendor_ids:
            clauses.append("vendor_id = ANY(%(vendor_ids)s)")
            binds["vendor_ids"] = list(params.vendor_ids)
        if params.invoice_status:
            clauses.append("invoice_status = ANY(%(invoice_status)s)")
            binds["invoice_status"] = list(params.invoice_status)
        if params.invoice_date_range:
            clauses.append(
                "invoice_date BETWEEN %(invoice_date_start)s AND %(invoice_date_end)s"
            )
            binds["invoice_date_start"] = params.invoice_date_range.start
            binds["invoice_date_end"] = params.invoice_date_range.end
        if params.min_amount is not None:
            clauses.append("invoice_total_amount >= %(min_amount)s")
            binds["min_amount"] = params.min_amount
        if params.max_amount is not None:
            clauses.append("invoice_total_amount <= %(max_amount)s")
            binds["max_amount"] = params.max_amount

        where = " AND ".join(clauses) if clauses else "1=1"
        binds["limit"] = min(params.limit or self.default_limit, self.max_limit)
        sql = (
            "SELECT invoice_id, invoice_number, matter_id, client_matter_id, "
            "vendor_id, invoice_date, billing_start_date, billing_end_date, "
            "invoice_status, approval_status, currency_code, invoice_total_amount, "
            "fee_total_amount, expense_total_amount, approved_amount, paid_amount, "
            "payment_date "
            f"FROM fact_invoice WHERE {where} ORDER BY invoice_date DESC LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
