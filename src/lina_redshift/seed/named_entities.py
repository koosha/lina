"""Hand-written named entities for golden-path tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from psycopg2.extensions import connection as PgConnection  # noqa: N812


@dataclass(frozen=True)
class LegalEntity:
    legal_entity_id: str
    legal_entity_name: str
    country_code: str
    entity_status: str = "active"


@dataclass(frozen=True)
class CostCenter:
    cost_center_id: str
    cost_center_name: str
    business_unit: str
    department: str
    active_status: str = "active"


@dataclass(frozen=True)
class Vendor:
    vendor_id: str
    vendor_name: str
    vendor_type: str
    vendor_status: str
    country_code: str
    default_currency_code: str
    preferred_panel_flag: bool
    source_system: str = "named_seed"


@dataclass(frozen=True)
class Matter:
    matter_id: str
    client_matter_id: str
    matter_name: str
    matter_type: str
    practice_area: str
    matter_status: str
    jurisdiction: str
    risk_level: str
    open_date: date
    close_date: date | None
    legal_entity_id: str
    business_unit: str
    matter_owner_user_id: str
    budget_amount: Decimal
    budget_currency_code: str
    source_system: str = "named_seed"


@dataclass(frozen=True)
class Timekeeper:
    timekeeper_id: str
    vendor_id: str
    timekeeper_name: str
    timekeeper_classification: str
    years_of_experience: int
    office_country_code: str
    active_status: str = "active"


@dataclass(frozen=True)
class TimekeeperRate:
    rate_id: str
    timekeeper_id: str
    vendor_id: str
    rate_type: str
    hourly_rate: Decimal
    currency_code: str
    effective_start_date: date
    effective_end_date: date | None
    approval_status: str = "approved"


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    invoice_number: str
    matter_id: str
    client_matter_id: str
    vendor_id: str
    invoice_date: date
    invoice_status: str
    currency_code: str
    invoice_total_amount: Decimal
    fee_total_amount: Decimal
    expense_total_amount: Decimal
    approved_amount: Decimal
    paid_amount: Decimal | None
    ledes_format: str = "LEDES_1998B"


@dataclass(frozen=True)
class LineItem:
    invoice_line_item_id: str
    invoice_id: str
    line_item_number: int
    matter_id: str
    client_matter_id: str
    vendor_id: str
    timekeeper_id: str | None
    line_item_date: date
    line_item_type: str
    task_code: str | None
    activity_code: str | None
    expense_code: str | None
    units: Decimal | None
    unit_rate: Decimal | None
    line_item_total_amount: Decimal
    currency_code: str
    usd_amount: Decimal
    fx_rate_to_usd: Decimal
    billing_guideline_flag: bool = False


NAMED_LEGAL_ENTITIES: list[LegalEntity] = [
    LegalEntity("le_acme_us", "Acme Corp US, Inc.", "US"),
    LegalEntity("le_acme_uk", "Acme Corp UK Ltd.", "GB"),
    LegalEntity("le_acme_de", "Acme Corp Deutschland GmbH", "DE"),
]

NAMED_COST_CENTERS: list[CostCenter] = [
    CostCenter("cc_legal_ops", "Legal Operations", "Legal", "Legal Ops"),
    CostCenter("cc_eng_platform", "Engineering Platform", "Engineering", "Platform"),
]

NAMED_VENDORS: list[Vendor] = [
    Vendor("vendor_walker", "Walker & Associates LLP", "law_firm",
           "preferred", "US", "USD", True),
    Vendor("vendor_jones", "Jones Privacy Law", "law_firm",
           "active", "US", "USD", False),
    Vendor("vendor_meridian", "Meridian Counsel UK", "law_firm",
           "active", "GB", "GBP", True),
]

NAMED_MATTERS: list[Matter] = [
    Matter("matter_acme_v_beta", "LIT-2024-001", "Acme v. Beta Litigation",
           "litigation", "Litigation", "open", "CA", "high",
           date(2024, 6, 1), None, "le_acme_us", "Enterprise",
           "user_jane_smith", Decimal("500000.00"), "USD"),
    Matter("matter_acme_privacy_review", "ADV-2024-042", "Acme Privacy Program Review",
           "advisory", "Privacy", "open", "US", "medium",
           date(2024, 9, 15), None, "le_acme_us", "Product",
           "user_alex_lee", Decimal("150000.00"), "USD"),
    Matter("matter_acme_employment_2023", "EMP-2023-007", "Smith v. Acme Employment",
           "employment", "Employment", "closed", "NY", "medium",
           date(2023, 1, 10), date(2024, 3, 30), "le_acme_us", "HR",
           "user_jane_smith", Decimal("75000.00"), "USD"),
]

NAMED_TIMEKEEPERS: list[Timekeeper] = [
    Timekeeper("tk_walker_partner", "vendor_walker", "Patricia Walker", "Partner", 22, "US"),
    Timekeeper("tk_walker_associate", "vendor_walker", "Roy Sanchez", "Associate", 5, "US"),
    Timekeeper("tk_jones_partner", "vendor_jones", "Daniel Jones", "Partner", 18, "US"),
    Timekeeper("tk_meridian_partner", "vendor_meridian", "Imogen Hart", "Partner", 25, "GB"),
    Timekeeper("tk_meridian_paralegal", "vendor_meridian", "Oliver Reed", "Paralegal", 8, "GB"),
]

NAMED_RATES: list[TimekeeperRate] = [
    TimekeeperRate("rate_walker_partner_2024", "tk_walker_partner", "vendor_walker",
                   "standard", Decimal("950"), "USD",
                   date(2024, 1, 1), date(2024, 12, 31)),
    TimekeeperRate("rate_walker_partner_2025", "tk_walker_partner", "vendor_walker",
                   "standard", Decimal("995"), "USD",
                   date(2025, 1, 1), None),
    TimekeeperRate("rate_walker_associate_2024", "tk_walker_associate", "vendor_walker",
                   "standard", Decimal("525"), "USD", date(2024, 1, 1), None),
    TimekeeperRate("rate_jones_partner_2024", "tk_jones_partner", "vendor_jones",
                   "discounted", Decimal("750"), "USD", date(2024, 1, 1), None),
    TimekeeperRate("rate_meridian_partner_2024", "tk_meridian_partner", "vendor_meridian",
                   "standard", Decimal("780"), "GBP", date(2024, 1, 1), None),
    TimekeeperRate("rate_meridian_paralegal_2024", "tk_meridian_paralegal", "vendor_meridian",
                   "standard", Decimal("220"), "GBP", date(2024, 1, 1), None),
]

NAMED_INVOICES: list[Invoice] = [
    Invoice("inv_walker_2024q3", "WALK-24-Q3-001", "matter_acme_v_beta", "LIT-2024-001",
            "vendor_walker", date(2024, 9, 30), "paid", "USD",
            Decimal("85000.00"), Decimal("82000.00"), Decimal("3000.00"),
            Decimal("80000.00"), Decimal("80000.00")),
    Invoice("inv_walker_2024q4", "WALK-24-Q4-002", "matter_acme_v_beta", "LIT-2024-001",
            "vendor_walker", date(2024, 12, 20), "approved", "USD",
            Decimal("105000.00"), Decimal("100000.00"), Decimal("5000.00"),
            Decimal("100000.00"), None),
    Invoice("inv_jones_2024q4", "JONES-24-Q4-001", "matter_acme_privacy_review",
            "ADV-2024-042", "vendor_jones", date(2024, 12, 15), "paid", "USD",
            Decimal("32000.00"), Decimal("31000.00"), Decimal("1000.00"),
            Decimal("30000.00"), Decimal("30000.00")),
    Invoice("inv_meridian_2025q1", "MER-25-Q1-001", "matter_acme_v_beta", "LIT-2024-001",
            "vendor_meridian", date(2025, 3, 31), "approved", "GBP",
            Decimal("18000.00"), Decimal("17500.00"), Decimal("500.00"),
            Decimal("17000.00"), None),
]

NAMED_LINE_ITEMS: list[LineItem] = [
    LineItem("li_walker_2024q3_1", "inv_walker_2024q3", 1, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_partner", date(2024, 8, 12), "fee",
             "L120", "A102", None, Decimal("12.0"), Decimal("950"),
             Decimal("11400.00"), "USD", Decimal("11400.00"), Decimal("1.0")),
    LineItem("li_walker_2024q3_2", "inv_walker_2024q3", 2, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_associate", date(2024, 8, 14), "fee",
             "L210", "A103", None, Decimal("40.0"), Decimal("525"),
             Decimal("21000.00"), "USD", Decimal("21000.00"), Decimal("1.0")),
    LineItem("li_walker_2024q3_3", "inv_walker_2024q3", 3, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", None, date(2024, 8, 20), "expense",
             None, None, "E110", None, None,
             Decimal("3000.00"), "USD", Decimal("3000.00"), Decimal("1.0")),
    LineItem("li_walker_2024q4_1", "inv_walker_2024q4", 1, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_partner", date(2024, 11, 5), "fee",
             "L240", "A103", None, Decimal("24.0"), Decimal("950"),
             Decimal("22800.00"), "USD", Decimal("22800.00"), Decimal("1.0"), True),
    LineItem("li_walker_2024q4_2", "inv_walker_2024q4", 2, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_associate", date(2024, 11, 8), "fee",
             "L310", "A104", None, Decimal("80.0"), Decimal("525"),
             Decimal("42000.00"), "USD", Decimal("42000.00"), Decimal("1.0")),
    LineItem("li_walker_2024q4_3", "inv_walker_2024q4", 3, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_partner", date(2024, 12, 1), "fee",
             "L160", "A106", None, Decimal("36.0"), Decimal("950"),
             Decimal("34200.00"), "USD", Decimal("34200.00"), Decimal("1.0")),
    LineItem("li_walker_2024q4_4", "inv_walker_2024q4", 4, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", None, date(2024, 12, 10), "expense",
             None, None, "E115", None, None,
             Decimal("5000.00"), "USD", Decimal("5000.00"), Decimal("1.0")),
    LineItem("li_jones_2024q4_1", "inv_jones_2024q4", 1, "matter_acme_privacy_review",
             "ADV-2024-042", "vendor_jones", "tk_jones_partner", date(2024, 11, 18), "fee",
             "L120", "A102", None, Decimal("32.0"), Decimal("750"),
             Decimal("24000.00"), "USD", Decimal("24000.00"), Decimal("1.0")),
    LineItem("li_jones_2024q4_2", "inv_jones_2024q4", 2, "matter_acme_privacy_review",
             "ADV-2024-042", "vendor_jones", "tk_jones_partner", date(2024, 11, 25), "fee",
             "L130", "A103", None, Decimal("9.0"), Decimal("750"),
             Decimal("6750.00"), "USD", Decimal("6750.00"), Decimal("1.0")),
    LineItem("li_jones_2024q4_3", "inv_jones_2024q4", 3, "matter_acme_privacy_review",
             "ADV-2024-042", "vendor_jones", None, date(2024, 12, 1), "expense",
             None, None, "E106", None, None,
             Decimal("1250.00"), "USD", Decimal("1250.00"), Decimal("1.0")),
    LineItem("li_meridian_2025q1_1", "inv_meridian_2025q1", 1, "matter_acme_v_beta",
             "LIT-2024-001", "vendor_meridian", "tk_meridian_partner", date(2025, 2, 14), "fee",
             "L320", "A104", None, Decimal("16.0"), Decimal("780"),
             Decimal("12480.00"), "GBP", Decimal("15600.00"), Decimal("1.25")),
    LineItem("li_meridian_2025q1_2", "inv_meridian_2025q1", 2, "matter_acme_v_beta",
             "LIT-2024-001", "vendor_meridian", "tk_meridian_paralegal", date(2025, 2, 20), "fee",
             "L320", "A110", None, Decimal("23.0"), Decimal("220"),
             Decimal("5060.00"), "GBP", Decimal("6325.00"), Decimal("1.25"), True),
]


def load_named_entities(connection: PgConnection) -> None:
    """Insert all named entities idempotently."""
    with connection.cursor() as cur:
        for e in NAMED_LEGAL_ENTITIES:
            cur.execute(
                "INSERT INTO dim_legal_entity (legal_entity_id, legal_entity_name, "
                "country_code, entity_status, created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (legal_entity_id) DO NOTHING",
                (e.legal_entity_id, e.legal_entity_name, e.country_code, e.entity_status),
            )
        for cc in NAMED_COST_CENTERS:
            cur.execute(
                "INSERT INTO dim_cost_center (cost_center_id, cost_center_name, "
                "business_unit, department, active_status, created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (cost_center_id) DO NOTHING",
                (cc.cost_center_id, cc.cost_center_name, cc.business_unit,
                 cc.department, cc.active_status),
            )
        for v in NAMED_VENDORS:
            cur.execute(
                "INSERT INTO dim_vendor (vendor_id, vendor_name, vendor_type, vendor_status, "
                "country_code, default_currency_code, preferred_panel_flag, "
                "created_at, updated_at, source_system) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s) "
                "ON CONFLICT (vendor_id) DO NOTHING",
                (v.vendor_id, v.vendor_name, v.vendor_type, v.vendor_status,
                 v.country_code, v.default_currency_code, v.preferred_panel_flag,
                 v.source_system),
            )
        for m in NAMED_MATTERS:
            cur.execute(
                "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
                "matter_type, practice_area, matter_status, jurisdiction, risk_level, "
                "open_date, close_date, legal_entity_id, business_unit, "
                "matter_owner_user_id, budget_amount, budget_currency_code, "
                "created_at, updated_at, source_system) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s) "
                "ON CONFLICT (matter_id) DO NOTHING",
                (m.matter_id, m.client_matter_id, m.matter_name, m.matter_type,
                 m.practice_area, m.matter_status, m.jurisdiction, m.risk_level,
                 m.open_date, m.close_date, m.legal_entity_id, m.business_unit,
                 m.matter_owner_user_id, m.budget_amount, m.budget_currency_code,
                 m.source_system),
            )
        for t in NAMED_TIMEKEEPERS:
            cur.execute(
                "INSERT INTO dim_timekeeper (timekeeper_id, vendor_id, timekeeper_name, "
                "timekeeper_classification, years_of_experience, office_country_code, "
                "active_status, created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (timekeeper_id) DO NOTHING",
                (t.timekeeper_id, t.vendor_id, t.timekeeper_name,
                 t.timekeeper_classification, t.years_of_experience,
                 t.office_country_code, t.active_status),
            )
        for r in NAMED_RATES:
            cur.execute(
                "INSERT INTO fact_timekeeper_rate (rate_id, timekeeper_id, vendor_id, "
                "rate_type, hourly_rate, currency_code, effective_start_date, "
                "effective_end_date, approval_status, created_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP) "
                "ON CONFLICT (rate_id) DO NOTHING",
                (r.rate_id, r.timekeeper_id, r.vendor_id, r.rate_type,
                 r.hourly_rate, r.currency_code, r.effective_start_date,
                 r.effective_end_date, r.approval_status),
            )
        for inv in NAMED_INVOICES:
            cur.execute(
                "INSERT INTO fact_invoice (invoice_id, invoice_number, matter_id, "
                "client_matter_id, vendor_id, invoice_date, invoice_status, "
                "currency_code, invoice_total_amount, fee_total_amount, "
                "expense_total_amount, approved_amount, paid_amount, ledes_format, "
                "created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (invoice_id) DO NOTHING",
                (inv.invoice_id, inv.invoice_number, inv.matter_id, inv.client_matter_id,
                 inv.vendor_id, inv.invoice_date, inv.invoice_status, inv.currency_code,
                 inv.invoice_total_amount, inv.fee_total_amount, inv.expense_total_amount,
                 inv.approved_amount, inv.paid_amount, inv.ledes_format),
            )
        for li in NAMED_LINE_ITEMS:
            cur.execute(
                "INSERT INTO fact_invoice_line_item (invoice_line_item_id, invoice_id, "
                "line_item_number, matter_id, client_matter_id, vendor_id, timekeeper_id, "
                "line_item_date, line_item_type, task_code, activity_code, expense_code, "
                "units, unit_rate, line_item_total_amount, currency_code, usd_amount, "
                "fx_rate_to_usd, billing_guideline_flag, created_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP) "
                "ON CONFLICT (invoice_line_item_id) DO NOTHING",
                (li.invoice_line_item_id, li.invoice_id, li.line_item_number,
                 li.matter_id, li.client_matter_id, li.vendor_id, li.timekeeper_id,
                 li.line_item_date, li.line_item_type, li.task_code, li.activity_code,
                 li.expense_code, li.units, li.unit_rate, li.line_item_total_amount,
                 li.currency_code, li.usd_amount, li.fx_rate_to_usd,
                 li.billing_guideline_flag),
            )
    connection.commit()
