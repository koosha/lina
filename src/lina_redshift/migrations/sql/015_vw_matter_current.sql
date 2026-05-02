CREATE OR REPLACE VIEW vw_matter_current AS
SELECT
    matter_id,
    client_matter_id,
    matter_name,
    matter_status,
    matter_type,
    practice_area,
    area_of_law_code,
    open_date,
    close_date,
    matter_owner_user_id,
    lead_inhouse_counsel_user_id,
    business_unit,
    cost_center_id,
    budget_amount,
    budget_currency_code
FROM dim_matter
WHERE matter_status <> 'archived';
