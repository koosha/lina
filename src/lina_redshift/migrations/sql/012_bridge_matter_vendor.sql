CREATE TABLE IF NOT EXISTS bridge_matter_vendor (
    matter_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    vendor_role varchar NOT NULL,
    engagement_start_date date,
    engagement_end_date date,
    active_flag boolean NOT NULL,
    PRIMARY KEY (matter_id, vendor_id, vendor_role)
)
DISTSTYLE KEY (matter_id)
SORTKEY (matter_id, vendor_id);
