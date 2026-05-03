CREATE TABLE IF NOT EXISTS fact_invoice_line_item (
    invoice_line_item_id varchar PRIMARY KEY,
    invoice_id varchar NOT NULL,
    line_item_number integer NOT NULL,
    matter_id varchar NOT NULL,
    client_matter_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    timekeeper_id varchar,
    line_item_date date NOT NULL,
    line_item_type varchar NOT NULL,
    task_code varchar,
    activity_code varchar,
    expense_code varchar,
    line_item_description varchar(max),
    units decimal(18, 4),
    unit_rate decimal(18, 4),
    line_item_total_amount decimal(18, 2) NOT NULL,
    adjustment_amount decimal(18, 2),
    approved_line_amount decimal(18, 2),
    currency_code char(3) NOT NULL,
    usd_amount decimal(18, 2),
    fx_rate_to_usd decimal(18, 8),
    review_status varchar,
    billing_guideline_flag boolean,
    billing_guideline_reason varchar,
    created_at timestamp NOT NULL
)
DISTSTYLE KEY (matter_id)
SORTKEY (line_item_date, vendor_id);
