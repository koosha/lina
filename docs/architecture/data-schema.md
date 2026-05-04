# Lina Data Schema

Canonical reference for the three data systems Lina queries through. Read this
when:

- Adding a new query template (you need to know what fields exist).
- Debugging a "0 rows" result (cross-check that the field is actually
  in the mapping/DDL).
- Reasoning about a follow-up that crosses systems (the cross-system links
  table at the end is the answer).

The supervisor never speaks to these stores directly — it routes through one
worker per system. User-facing names: **Matter & Spend** for Redshift,
**User Profiles** for OpenSearch users, **Outside Counsel** for OpenSearch
vendors.

---

## Subsystem C — Matter & Spend (Redshift)

Schema: `legal_matter_spend` on Redshift Serverless. 18 numbered SQL
migrations under [`src/lina_redshift/migrations/sql/`](../../src/lina_redshift/migrations/sql/).
Star schema: 6 dims, 5 facts, 3 bridges, 1 view, 3 materialized views.

### Dimensions (slowly-changing reference data)

| Table | PK | Notable columns |
| --- | --- | --- |
| `dim_legal_entity` | `legal_entity_id` | `legal_entity_name`, `country_code`, `entity_status` |
| `dim_cost_center` | `cost_center_id` | `cost_center_name`, `business_unit`, `department` |
| `dim_billing_code` | `billing_code_id` | `code`, `code_type`, `code_set`, `description` (UTBMS task/activity/expense codes) |
| `dim_vendor` | `vendor_id` | `vendor_name`, `vendor_type`, `default_currency_code`, `preferred_panel_flag` |
| `dim_matter` | `matter_id` | `client_matter_id`, `matter_name`, `matter_status`, `practice_area`, `open_date`, `budget_amount`, `matter_owner_user_id`, `lead_inhouse_counsel_user_id`, `invoice_approver_user_id`, `legal_entity_id`, `cost_center_id` |
| `dim_timekeeper` | `timekeeper_id` | `vendor_id`, `timekeeper_name`, `timekeeper_classification` (Partner/Associate/Paralegal/etc.), `years_of_experience` |

### Facts (event-level data)

| Table | PK | Grain | Key FKs |
| --- | --- | --- | --- |
| `fact_timekeeper_rate` | `rate_id` | One row per (timekeeper, rate_type, effective period) | `timekeeper_id`, `vendor_id`, `matter_id` (nullable — matter-specific overrides) |
| `fact_invoice` | `invoice_id` | One row per invoice header | `matter_id`, `vendor_id`, `client_matter_id` |
| `fact_invoice_line_item` | `invoice_line_item_id` | One row per LEDES line | `invoice_id`, `matter_id`, `vendor_id`, `timekeeper_id` |
| `fact_matter_budget` | `matter_budget_id` | One row per (matter, budget_version) | `matter_id` |
| `fact_accrual` | `accrual_id` | One row per (matter, accounting_period) | `matter_id`, `vendor_id` |

### Bridges (many-to-many relationships)

| Table | Composite PK | Purpose |
| --- | --- | --- |
| `bridge_matter_vendor` | `(matter_id, vendor_id, vendor_role)` | Which vendors are engaged on which matters and in what role (lead, conflict, etc.) |
| `bridge_matter_person` | `(matter_id, person_id, person_source, person_role)` | Maps internal users (`person_source='users'`) and outside lawyers (`person_source='vendors'`) to the matters they touch |
| `bridge_matter_allocation` | `(matter_id, legal_entity_id, cost_center_id, gl_account, effective_start_date)` | Cost allocations across legal entities and cost centers |

### View

| Object | Definition | Purpose |
| --- | --- | --- |
| `vw_matter_current` | `SELECT … FROM dim_matter WHERE matter_status <> 'archived'` | Live (non-archived) matters with a curated subset of `dim_matter` columns |

### Materialized views (auto-refreshed)

Each MV is grouped by `fiscal_period = to_char(line_item_date, 'YYYY-"Q"Q')` so
queries can filter to a single quarter without scanning the line-item fact.

| MV | Grain | Output highlights |
| --- | --- | --- |
| `mv_matter_spend_summary` | `(matter_id, fiscal_period)` | Approved/billed/paid amounts, fee/expense split, invoice count, vendor count, budget remaining, budget utilization % |
| `mv_vendor_spend_summary` | `(vendor_id, fiscal_period)` | Approved/billed totals, matter/invoice counts, average hourly rate, partner vs associate hours, billing-guideline-flag count |
| `mv_timekeeper_rate_analysis` | `(timekeeper_id, vendor_id, fiscal_period)` | Billed hours/amount, average billed rate, approved rate from `fact_timekeeper_rate`, rate variance amount and % |

### Query templates routed to this subsystem

In [`src/lina_redshift/templates/`](../../src/lina_redshift/templates/):
`matter_lookup`, `matter_spend_summary`, `vendor_spend_summary`,
`timekeeper_rate_analysis`, `invoice_search`, `line_item_detail`.

---

## Subsystem A — User Profiles (OpenSearch)

Single index `corp_user_profiles_v1`, mapping at
[`src/lina_users/indices/mappings/001_corp_user_profiles_v1.json`](../../src/lina_users/indices/mappings/001_corp_user_profiles_v1.json).
Document `_id` = `user_id` for idempotent upserts.

### Field mapping

| Field | Type | Notes |
| --- | --- | --- |
| `user_id` | keyword | Matches `dim_matter.matter_owner_user_id` and `bridge_matter_person.person_id` (when `person_source='users'`) |
| `employee_id` | keyword | HRIS identifier |
| `email` | keyword | Exact-match only (use `email_text` for fuzzy match) |
| `email_text` | text | Free-text variant for `multi_match` queries |
| `first_name`, `last_name`, `display_name` | text + .keyword | Multi-field — text for search, keyword for terms aggregations |
| `phone_number`, `mobile_number` | keyword | |
| `job_title` | text + .keyword | Search and exact-bucket |
| `department`, `business_unit`, `cost_center` | keyword | Filterable; `cost_center` aligns with `dim_cost_center.cost_center_id` |
| `manager_user_id` | keyword | Self-reference into the same index — supports manager_chain template |
| `office_location_id` | keyword | |
| `corporate_address` | object | `address_line_1/_2`, `city`, `state_province`, `postal_code`, `country_code`, `full_address` |
| `region` | keyword | AMER / EMEA / APAC |
| `country_code`, `timezone` | keyword | |
| `user_status` | keyword | `active` / `inactive` |
| `user_type` | keyword | `employee` / `contractor` / etc. |
| `roles` | keyword (array) | Functional roles — `legal_ops`, `inhouse_counsel`, etc. |
| `permission_tags` | keyword (array) | `matter_owner`, `approver`, `privacy_reviewer`, etc. |
| `legal_team_role` | keyword | `senior_counsel` / `paralegal` / etc. |
| `practice_area_focus` | keyword (array) | Litigation / Privacy / Employment |
| `created_at`, `updated_at` | date | |
| `source_system` | keyword | Origin HRIS |

### Query templates

In [`src/lina_users/templates/`](../../src/lina_users/templates/):
`user_lookup`, `user_search`, `people_filter`, `manager_chain`. The
`manager_chain` template is special — it walks `manager_user_id` self-links
to build a reporting tree.

---

## Subsystem B — Outside Counsel (OpenSearch)

Single index `vendor_lawyer_profiles_v1`, mapping at
[`src/lina_vendors/indices/mappings/001_vendor_lawyer_profiles_v1.json`](../../src/lina_vendors/indices/mappings/001_vendor_lawyer_profiles_v1.json).
Document `_id` = `timekeeper_id` for idempotent upserts.

### Field mapping

| Field | Type | Notes |
| --- | --- | --- |
| `timekeeper_id` | keyword | **Same identity as Redshift `dim_timekeeper.timekeeper_id`** — this is the cross-system link |
| `vendor_id` | keyword | **Same identity as Redshift `dim_vendor.vendor_id`** |
| `vendor_name` | text + .keyword | Firm name |
| `first_name`, `last_name`, `display_name` | text + .keyword | |
| `email` | keyword | |
| `phone_number` | keyword | |
| `office_country_code`, `office_state_province`, `office_city`, `office_postal_code` | keyword | |
| `bar_admissions` | keyword (array) | Jurisdictions where the lawyer is admitted to the bar |
| `jurisdictions` | keyword (array) | Practice jurisdictions (broader than bar) |
| `industries` | keyword (array) | Industry experience tags |
| `practice_areas` | keyword (array) | Litigation, M&A, Privacy, Tax, etc. |
| `currency_code` | keyword | ISO 4217 |
| `active_status` | keyword | `Active` / `Inactive` |
| `timekeeper_classification` | keyword | Partner / Associate / Counsel / Paralegal — **redundantly stored in Redshift `dim_timekeeper`** so single-system spend queries don't need a join |
| `expertise_summary` | text | Free-text — supports `practice_area_match` template |
| `representative_matters_summary` | text | Free-text — supports lawyer-search by past-work signal |
| `standard_hourly_rate`, `effective_hourly_rate` | scaled_float (×100) | List-rate vs. negotiated; both stored in cents-as-int for exactness |
| `years_of_experience` | integer | |
| `rate_history` | nested | Array of `{rate_type, hourly_rate, currency_code, effective_start_date, effective_end_date, matter_id, approval_status}` — nested so per-rate filters don't cross items |
| `profile_sources` | nested | Array of `{source_name, source_record_id, last_synced_at}` — provenance |
| `rate_effective_start_date`, `rate_effective_end_date`, `created_at`, `updated_at` | date | |

### Query templates

In [`src/lina_vendors/templates/`](../../src/lina_vendors/templates/):
`timekeeper_lookup`, `lawyer_search`, `practice_area_match`,
`outside_counsel_filter`.

---

## Cross-system links

The supervisor's whole purpose is to compose answers across these stores.
Every cross-system follow-up rides on one of these shared identifiers:

| Identifier | Where it lives | What it links |
| --- | --- | --- |
| `user_id` | Redshift: `dim_matter.matter_owner_user_id`, `dim_matter.lead_inhouse_counsel_user_id`, `dim_matter.invoice_approver_user_id`, `fact_matter_budget.submitted_by_user_id`/`approved_by_user_id`, `fact_timekeeper_rate.approved_by_user_id`, `bridge_matter_person.person_id` (when `person_source='users'`) <br> OpenSearch: `corp_user_profiles_v1._id` (= `user_id`), `manager_user_id` | Matter ownership and approver chains in Redshift → person details in User Profiles. Manager chain queries are pure User Profiles (self-link). |
| `vendor_id` | Redshift: `dim_vendor.vendor_id`, `dim_timekeeper.vendor_id`, `fact_invoice.vendor_id`, `fact_invoice_line_item.vendor_id`, `fact_timekeeper_rate.vendor_id`, `bridge_matter_vendor.vendor_id` <br> OpenSearch: `vendor_lawyer_profiles_v1.vendor_id` | Vendor spend in Redshift → firm and lawyer details in Outside Counsel. |
| `timekeeper_id` | Redshift: `dim_timekeeper.timekeeper_id`, `fact_invoice_line_item.timekeeper_id`, `fact_timekeeper_rate.timekeeper_id`, `mv_timekeeper_rate_analysis.timekeeper_id` <br> OpenSearch: `vendor_lawyer_profiles_v1._id` (= `timekeeper_id`) | Billed hours and rate variance in Redshift → bar admissions, practice areas, expertise summary in Outside Counsel. |
| `matter_id` | Redshift everywhere; mentioned in Outside Counsel `rate_history.matter_id` for matter-specific rate overrides | Matter-scoped lawyer rate history is the only place `matter_id` shows up outside Redshift. |
| `cost_center_id` | Redshift `dim_cost_center` and `dim_matter` <br> OpenSearch User Profiles `cost_center` | Cost-center attribution joins matters to people. |

The supervisor doesn't enforce these joins as constraints — they're "soft" foreign keys. A `bridge_matter_person.person_id` that doesn't resolve in either OpenSearch index just produces an empty packet and the supervisor explains that the person can't be found.

### Composition examples

- **Spend by partner on a matter:** Redshift `mv_vendor_spend_summary` joined to Outside Counsel `vendor_lawyer_profiles_v1` on `vendor_id`, filtered to `timekeeper_classification = "Partner"`.
- **Matter owner detail:** Redshift `dim_matter.matter_owner_user_id` looked up in User Profiles `corp_user_profiles_v1.user_id`.
- **Rate variance with attribution:** Redshift `mv_timekeeper_rate_analysis` joined to Outside Counsel on `timekeeper_id` for the lawyer's standard rate.

### Change ownership

Each store has its own owner of truth:

- Redshift is sourced from the LEDES e-billing pipeline + the matter-management system. Mutations are batch ETL.
- User Profiles is sourced from HRIS. Updates are typically nightly.
- Outside Counsel is sourced from the panel-management system + manual curation. Updates are sporadic.

Lina is read-only against all three. There's no write path through the supervisor or the workers.
