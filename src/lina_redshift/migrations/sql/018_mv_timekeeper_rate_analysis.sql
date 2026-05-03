CREATE MATERIALIZED VIEW mv_timekeeper_rate_analysis
AUTO REFRESH YES
AS
SELECT
    li.timekeeper_id,
    li.vendor_id,
    to_char(li.line_item_date, 'YYYY-"Q"Q') AS fiscal_period,
    sum(li.units) AS billed_hours,
    sum(li.line_item_total_amount) AS billed_amount,
    case when sum(li.units) > 0
         then sum(li.line_item_total_amount) / sum(li.units)
         else 0
    end AS average_billed_rate,
    max(r.hourly_rate) AS approved_rate,
    sum(li.line_item_total_amount)
        - (max(r.hourly_rate) * sum(li.units)) AS rate_variance_amount,
    case when max(r.hourly_rate) > 0 AND sum(li.units) > 0
         then (sum(li.line_item_total_amount) - (max(r.hourly_rate) * sum(li.units)))
              / (max(r.hourly_rate) * sum(li.units))
         else 0
    end AS rate_variance_percent
FROM fact_invoice_line_item li
LEFT JOIN fact_timekeeper_rate r ON li.timekeeper_id = r.timekeeper_id
    AND r.approval_status = 'approved'
    AND li.line_item_date BETWEEN r.effective_start_date
        AND coalesce(r.effective_end_date, DATE '9999-12-31')
WHERE li.line_item_type = 'fee' AND li.timekeeper_id IS NOT NULL
GROUP BY li.timekeeper_id, li.vendor_id, to_char(li.line_item_date, 'YYYY-"Q"Q');
