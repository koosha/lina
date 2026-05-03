CREATE TABLE IF NOT EXISTS bridge_matter_allocation (
    matter_id varchar NOT NULL,
    legal_entity_id varchar,
    cost_center_id varchar,
    gl_account varchar,
    allocation_percentage decimal(9, 6) NOT NULL,
    effective_start_date date NOT NULL,
    effective_end_date date,
    active_flag boolean NOT NULL,
    PRIMARY KEY (matter_id, legal_entity_id, cost_center_id, gl_account, effective_start_date)
)
DISTKEY (matter_id)
SORTKEY (matter_id, effective_start_date);
