CREATE TABLE IF NOT EXISTS fact_timekeeper_rate (
    rate_id varchar PRIMARY KEY,
    timekeeper_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    matter_id varchar,
    rate_type varchar NOT NULL,
    hourly_rate decimal(18, 4) NOT NULL,
    currency_code char(3) NOT NULL,
    effective_start_date date NOT NULL,
    effective_end_date date,
    approval_status varchar NOT NULL,
    approved_by_user_id varchar,
    approved_at timestamp,
    created_at timestamp NOT NULL
)
DISTSTYLE KEY (timekeeper_id)
SORTKEY (timekeeper_id, effective_start_date);
