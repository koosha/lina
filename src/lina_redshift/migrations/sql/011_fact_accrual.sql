CREATE TABLE IF NOT EXISTS fact_accrual (
    accrual_id varchar PRIMARY KEY,
    matter_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    accounting_period varchar NOT NULL,
    period_start_date date NOT NULL,
    period_end_date date NOT NULL,
    estimated_unbilled_amount decimal(18, 2) NOT NULL,
    currency_code char(3) NOT NULL,
    submitted_by varchar,
    submitted_at timestamp,
    accrual_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTKEY (matter_id)
SORTKEY (period_start_date, matter_id);
