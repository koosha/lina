CREATE TABLE IF NOT EXISTS bridge_matter_person (
    matter_id varchar NOT NULL,
    person_id varchar NOT NULL,
    person_source varchar NOT NULL,
    person_role varchar NOT NULL,
    start_date date,
    end_date date,
    active_flag boolean NOT NULL,
    PRIMARY KEY (matter_id, person_id, person_source, person_role)
)
DISTSTYLE KEY (matter_id)
SORTKEY (matter_id, person_source);
