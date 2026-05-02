CREATE MATERIALIZED VIEW mv_vendor_spend_summary AS
SELECT
    li.vendor_id,
    to_char(li.line_item_date, 'YYYY-"Q"Q') AS fiscal_period,
    sum(li.line_item_total_amount) AS total_billed_amount,
    sum(coalesce(li.approved_line_amount, li.line_item_total_amount)) AS total_approved_amount,
    count(distinct li.matter_id) AS matter_count,
    count(distinct li.invoice_id) AS invoice_count,
    case when sum(case when li.line_item_type = 'fee' then li.units else 0 end) > 0
         then sum(case when li.line_item_type = 'fee' then li.line_item_total_amount else 0 end)
              / sum(case when li.line_item_type = 'fee' then li.units else 0 end)
         else 0
    end AS average_hourly_rate,
    sum(case when li.line_item_type = 'fee' AND tk.timekeeper_classification = 'Partner'
             then li.units else 0 end) AS partner_hours,
    sum(case when li.line_item_type = 'fee' AND tk.timekeeper_classification = 'Associate'
             then li.units else 0 end) AS associate_hours,
    sum(case when li.line_item_type = 'expense' then li.line_item_total_amount else 0 end) AS expense_amount,
    sum(coalesce(li.adjustment_amount, 0)) AS adjustment_amount,
    sum(case when li.billing_guideline_flag then 1 else 0 end) AS billing_guideline_flag_count
FROM fact_invoice_line_item li
LEFT JOIN dim_timekeeper tk ON li.timekeeper_id = tk.timekeeper_id
GROUP BY li.vendor_id, to_char(li.line_item_date, 'YYYY-"Q"Q')
AUTO REFRESH YES;
