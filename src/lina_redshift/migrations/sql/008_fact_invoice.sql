CREATE TABLE IF NOT EXISTS fact_invoice (
    invoice_id varchar PRIMARY KEY,
    invoice_number varchar NOT NULL,
    matter_id varchar NOT NULL,
    client_matter_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    invoice_date date NOT NULL,
    billing_start_date date,
    billing_end_date date,
    received_date date,
    posted_date date,
    invoice_status varchar NOT NULL,
    approval_status varchar,
    currency_code char(3) NOT NULL,
    invoice_total_amount decimal(18, 2) NOT NULL,
    fee_total_amount decimal(18, 2),
    expense_total_amount decimal(18, 2),
    tax_total_amount decimal(18, 2),
    discount_total_amount decimal(18, 2),
    approved_amount decimal(18, 2),
    paid_amount decimal(18, 2),
    payment_date date,
    ledes_format varchar,
    source_file_id varchar,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE KEY (matter_id)
SORTKEY (invoice_date, vendor_id);
