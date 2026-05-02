CREATE TABLE IF NOT EXISTS dim_billing_code (
    billing_code_id varchar PRIMARY KEY,
    code varchar NOT NULL,
    code_type varchar NOT NULL,
    code_set varchar NOT NULL,
    description varchar NOT NULL,
    active_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE ALL
SORTKEY (code_set, code);
