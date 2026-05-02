CREATE TABLE IF NOT EXISTS dim_vendor (
    vendor_id varchar PRIMARY KEY,
    vendor_name varchar NOT NULL,
    vendor_type varchar NOT NULL,
    vendor_status varchar NOT NULL,
    primary_contact_name varchar,
    primary_contact_email varchar,
    billing_contact_email varchar,
    country_code char(2),
    default_currency_code char(3),
    preferred_panel_flag boolean,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL,
    source_system varchar NOT NULL
)
DISTSTYLE ALL
SORTKEY (vendor_id);
