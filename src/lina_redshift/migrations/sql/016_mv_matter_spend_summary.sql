CREATE MATERIALIZED VIEW mv_matter_spend_summary
AUTO REFRESH YES
AS
SELECT
    li.matter_id,
    to_char(li.line_item_date, 'YYYY-"Q"Q') AS fiscal_period,
    sum(li.line_item_total_amount) AS total_billed_amount,
    sum(coalesce(li.approved_line_amount, li.line_item_total_amount)) AS total_approved_amount,
    sum(coalesce(inv.paid_amount, 0)) AS total_paid_amount,
    sum(case when li.line_item_type = 'fee' then li.line_item_total_amount else 0 end) AS fee_amount,
    sum(case when li.line_item_type = 'expense' then li.line_item_total_amount else 0 end) AS expense_amount,
    sum(coalesce(inv.tax_total_amount, 0)) AS tax_amount,
    sum(coalesce(li.adjustment_amount, 0)) AS adjustment_amount,
    count(distinct li.invoice_id) AS invoice_count,
    count(distinct li.vendor_id) AS vendor_count,
    count(distinct li.timekeeper_id) AS timekeeper_count,
    coalesce(max(b.budget_amount), 0) AS budget_amount,
    coalesce(max(b.budget_amount), 0) - sum(coalesce(li.approved_line_amount, li.line_item_total_amount)) AS budget_remaining,
    case when coalesce(max(b.budget_amount), 0) > 0
         then sum(coalesce(li.approved_line_amount, li.line_item_total_amount)) / max(b.budget_amount)
         else 0
    end AS budget_utilization_percent
FROM fact_invoice_line_item li
LEFT JOIN fact_invoice inv ON li.invoice_id = inv.invoice_id
LEFT JOIN fact_matter_budget b ON li.matter_id = b.matter_id
    AND b.budget_status = 'approved'
    AND li.line_item_date BETWEEN b.budget_period_start_date AND b.budget_period_end_date
GROUP BY li.matter_id, to_char(li.line_item_date, 'YYYY-"Q"Q');
