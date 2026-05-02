CREATE TABLE IF NOT EXISTS dim_legal_entity (
    legal_entity_id varchar PRIMARY KEY,
    legal_entity_name varchar NOT NULL,
    country_code char(2),
    entity_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE ALL
SORTKEY (legal_entity_id);
