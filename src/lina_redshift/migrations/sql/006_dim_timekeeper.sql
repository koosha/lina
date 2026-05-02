CREATE TABLE IF NOT EXISTS dim_timekeeper (
    timekeeper_id varchar PRIMARY KEY,
    vendor_id varchar NOT NULL,
    timekeeper_name varchar NOT NULL,
    timekeeper_email varchar,
    timekeeper_classification varchar NOT NULL,
    years_of_experience integer,
    office_city varchar,
    office_state_province varchar,
    office_country_code char(2),
    active_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE ALL
SORTKEY (vendor_id, timekeeper_id);
