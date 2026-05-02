CREATE TABLE IF NOT EXISTS dim_cost_center (
    cost_center_id varchar PRIMARY KEY,
    cost_center_name varchar NOT NULL,
    business_unit varchar,
    department varchar,
    active_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE ALL
SORTKEY (cost_center_id);
