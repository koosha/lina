CREATE TABLE IF NOT EXISTS fact_matter_budget (
    matter_budget_id varchar PRIMARY KEY,
    matter_id varchar NOT NULL,
    budget_version integer NOT NULL,
    budget_period_start_date date NOT NULL,
    budget_period_end_date date NOT NULL,
    budget_amount decimal(18, 2) NOT NULL,
    currency_code char(3) NOT NULL,
    budget_status varchar NOT NULL,
    submitted_by_user_id varchar,
    approved_by_user_id varchar,
    approved_at timestamp,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE KEY (matter_id)
SORTKEY (matter_id, budget_version);
