"""Deterministic Faker-driven bulk seed generator (fixed seed = 42)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.seed.named_entities import (
    Invoice,
    LineItem,
    Matter,
    Timekeeper,
    TimekeeperRate,
    Vendor,
)

_SEED = 42
_PRACTICE_AREAS = (
    "Litigation",
    "Privacy",
    "Employment",
    "M&A",
    "IP",
    "Regulatory",
    "Real Estate",
    "Tax",
)
_MATTER_TYPES = ("litigation", "advisory", "transactional", "regulatory", "employment")
_MATTER_STATUSES = ("open", "open", "open", "open", "closed", "on_hold")  # weighted
_VENDOR_TYPES = ("law_firm", "law_firm", "law_firm", "consultant", "expert", "ediscovery")
_CLASSIFICATIONS_WEIGHTED = (
    *(["Partner"] * 30),
    *(["Associate"] * 50),
    *(["Paralegal"] * 15),
    *(["Counsel"] * 5),
)
_CURRENCY_WEIGHTS = (
    *(["USD"] * 80),
    *(["GBP"] * 10),
    *(["EUR"] * 5),
    *(["CAD"] * 2),
    *(["AUD"] * 2),
    *(["JPY"] * 1),
)
_FX_TO_USD = {
    "USD": Decimal("1.0"),
    "GBP": Decimal("1.25"),
    "EUR": Decimal("1.08"),
    "CAD": Decimal("0.74"),
    "AUD": Decimal("0.66"),
    "JPY": Decimal("0.0067"),
}
_TASK_CODES = ("L100", "L120", "L210", "L240", "L310", "L320", "L330", "L410")
_ACTIVITY_CODES = ("A101", "A102", "A103", "A104", "A106", "A109")
_EXPENSE_CODES = ("E101", "E106", "E110", "E111", "E115")


@dataclass
class GeneratedSeed:
    matters: list[Matter] = field(default_factory=list)
    vendors: list[Vendor] = field(default_factory=list)
    timekeepers: list[Timekeeper] = field(default_factory=list)
    rates: list[TimekeeperRate] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    line_items: list[LineItem] = field(default_factory=list)


def generate_seed() -> GeneratedSeed:
    fake = Faker("en_US")
    Faker.seed(_SEED)
    rng = random.Random(_SEED)

    seed = GeneratedSeed()

    for i in range(25):
        seed.vendors.append(
            Vendor(
                vendor_id=f"vendor_gen_{i:03d}",
                vendor_name=f"{fake.last_name()} & {fake.last_name()} {rng.choice(['LLP', 'PLLC', 'PC'])}",
                vendor_type=rng.choice(_VENDOR_TYPES),
                vendor_status=rng.choice(("active", "active", "active", "preferred", "inactive")),
                country_code=rng.choice(("US", "US", "US", "GB", "DE", "CA")),
                default_currency_code=rng.choice(("USD", "USD", "USD", "GBP", "EUR")),
                preferred_panel_flag=rng.random() < 0.4,
                source_system="generator_seed",
            )
        )

    for j in range(200):
        v = rng.choice(seed.vendors)
        seed.timekeepers.append(
            Timekeeper(
                timekeeper_id=f"tk_gen_{j:04d}",
                vendor_id=v.vendor_id,
                timekeeper_name=fake.name(),
                timekeeper_classification=rng.choice(_CLASSIFICATIONS_WEIGHTED),
                years_of_experience=rng.randint(1, 35),
                office_country_code=v.country_code,
            )
        )
        rate_value = {
            "Partner": rng.randint(700, 1200),
            "Associate": rng.randint(350, 650),
            "Paralegal": rng.randint(150, 280),
            "Counsel": rng.randint(550, 850),
        }[seed.timekeepers[-1].timekeeper_classification]
        seed.rates.append(
            TimekeeperRate(
                rate_id=f"rate_gen_{j:04d}",
                timekeeper_id=seed.timekeepers[-1].timekeeper_id,
                vendor_id=v.vendor_id,
                rate_type="standard",
                hourly_rate=Decimal(str(rate_value)),
                currency_code=v.default_currency_code,
                effective_start_date=date(2023, 1, 1),
                effective_end_date=None,
            )
        )

    for k in range(100):
        open_date = _random_date(rng, date(2023, 1, 1), date(2025, 3, 31))
        status = rng.choice(_MATTER_STATUSES)
        close_date = _random_date(rng, open_date, date(2025, 6, 30)) if status == "closed" else None
        seed.matters.append(
            Matter(
                matter_id=f"matter_gen_{k:03d}",
                client_matter_id=f"GEN-{2023 + k % 3}-{k:04d}",
                matter_name=f"{fake.company()} {rng.choice(['Litigation', 'Review', 'Investigation', 'Advisory'])}",
                matter_type=rng.choice(_MATTER_TYPES),
                practice_area=rng.choice(_PRACTICE_AREAS),
                matter_status=status,
                jurisdiction=rng.choice(("CA", "NY", "TX", "DE", "US", "GB")),
                risk_level=rng.choice(("low", "medium", "medium", "high")),
                open_date=open_date,
                close_date=close_date,
                legal_entity_id=rng.choice(("le_acme_us", "le_acme_uk", "le_acme_de")),
                business_unit=rng.choice(("Enterprise", "Product", "HR", "Finance")),
                matter_owner_user_id=f"user_gen_{rng.randint(0, 49):03d}",
                budget_amount=Decimal(str(rng.randint(50_000, 1_500_000))),
                budget_currency_code="USD",
                source_system="generator_seed",
            )
        )

    line_item_idx = 0
    for invoice_idx in range(600):
        matter = rng.choice(seed.matters)
        possible_vendors = [
            t for t in seed.timekeepers if t.vendor_id in {v.vendor_id for v in seed.vendors}
        ]
        vendor_id = rng.choice(possible_vendors).vendor_id
        invoice_date = _random_date(rng, date(2023, 1, 1), date(2025, 6, 30))
        currency = rng.choice(_CURRENCY_WEIGHTS)

        per_invoice_lines = rng.randint(8, 12)
        line_items_for_invoice: list[LineItem] = []
        running_fee = Decimal("0")
        running_expense = Decimal("0")
        for line_no in range(1, per_invoice_lines + 1):
            is_fee = rng.random() < 0.85
            tk_choices = [t for t in seed.timekeepers if t.vendor_id == vendor_id]
            tk = rng.choice(tk_choices) if tk_choices else None
            if is_fee and tk is not None:
                hours = Decimal(str(round(rng.uniform(0.5, 8.0), 1)))
                rate = next(
                    (r.hourly_rate for r in seed.rates if r.timekeeper_id == tk.timekeeper_id),
                    Decimal("500"),
                )
                amount = (hours * rate).quantize(Decimal("0.01"))
                running_fee += amount
                line_items_for_invoice.append(
                    LineItem(
                        invoice_line_item_id=f"li_gen_{line_item_idx:06d}",
                        invoice_id=f"inv_gen_{invoice_idx:05d}",
                        line_item_number=line_no,
                        matter_id=matter.matter_id,
                        client_matter_id=matter.client_matter_id,
                        vendor_id=vendor_id,
                        timekeeper_id=tk.timekeeper_id,
                        line_item_date=invoice_date - timedelta(days=rng.randint(0, 60)),
                        line_item_type="fee",
                        task_code=rng.choice(_TASK_CODES),
                        activity_code=rng.choice(_ACTIVITY_CODES),
                        expense_code=None,
                        units=hours,
                        unit_rate=rate,
                        line_item_total_amount=amount,
                        currency_code=currency,
                        usd_amount=(amount * _FX_TO_USD[currency]).quantize(Decimal("0.01")),
                        fx_rate_to_usd=_FX_TO_USD[currency],
                        billing_guideline_flag=rng.random() < 0.05,
                    )
                )
            else:
                amount = Decimal(str(round(rng.uniform(50, 2500), 2)))
                running_expense += amount
                line_items_for_invoice.append(
                    LineItem(
                        invoice_line_item_id=f"li_gen_{line_item_idx:06d}",
                        invoice_id=f"inv_gen_{invoice_idx:05d}",
                        line_item_number=line_no,
                        matter_id=matter.matter_id,
                        client_matter_id=matter.client_matter_id,
                        vendor_id=vendor_id,
                        timekeeper_id=None,
                        line_item_date=invoice_date - timedelta(days=rng.randint(0, 30)),
                        line_item_type="expense",
                        task_code=None,
                        activity_code=None,
                        expense_code=rng.choice(_EXPENSE_CODES),
                        units=None,
                        unit_rate=None,
                        line_item_total_amount=amount,
                        currency_code=currency,
                        usd_amount=(amount * _FX_TO_USD[currency]).quantize(Decimal("0.01")),
                        fx_rate_to_usd=_FX_TO_USD[currency],
                    )
                )
            line_item_idx += 1

        invoice_total = running_fee + running_expense
        seed.invoices.append(
            Invoice(
                invoice_id=f"inv_gen_{invoice_idx:05d}",
                invoice_number=f"GEN-{invoice_idx:06d}",
                matter_id=matter.matter_id,
                client_matter_id=matter.client_matter_id,
                vendor_id=vendor_id,
                invoice_date=invoice_date,
                invoice_status=rng.choice(("paid", "approved", "under_review", "received")),
                currency_code=currency,
                invoice_total_amount=invoice_total.quantize(Decimal("0.01")),
                fee_total_amount=running_fee.quantize(Decimal("0.01")),
                expense_total_amount=running_expense.quantize(Decimal("0.01")),
                approved_amount=invoice_total.quantize(Decimal("0.01")),
                paid_amount=invoice_total.quantize(Decimal("0.01")) if rng.random() < 0.7 else None,
            )
        )
        seed.line_items.extend(line_items_for_invoice)

    return seed


def _random_date(rng: random.Random, start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def load_bulk_generated(connection: PgConnection) -> None:
    """Generate the bulk seed and insert. Idempotent via ON CONFLICT."""
    seed = generate_seed()
    with connection.cursor() as cur:
        for v in seed.vendors:
            cur.execute(
                "INSERT INTO dim_vendor (vendor_id, vendor_name, vendor_type, "
                "vendor_status, country_code, default_currency_code, "
                "preferred_panel_flag, created_at, updated_at, source_system) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP, %s) ON CONFLICT (vendor_id) DO NOTHING",
                (
                    v.vendor_id,
                    v.vendor_name,
                    v.vendor_type,
                    v.vendor_status,
                    v.country_code,
                    v.default_currency_code,
                    v.preferred_panel_flag,
                    v.source_system,
                ),
            )
        for t in seed.timekeepers:
            cur.execute(
                "INSERT INTO dim_timekeeper (timekeeper_id, vendor_id, timekeeper_name, "
                "timekeeper_classification, years_of_experience, office_country_code, "
                "active_status, created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (timekeeper_id) DO NOTHING",
                (
                    t.timekeeper_id,
                    t.vendor_id,
                    t.timekeeper_name,
                    t.timekeeper_classification,
                    t.years_of_experience,
                    t.office_country_code,
                    t.active_status,
                ),
            )
        for r in seed.rates:
            cur.execute(
                "INSERT INTO fact_timekeeper_rate (rate_id, timekeeper_id, vendor_id, "
                "rate_type, hourly_rate, currency_code, effective_start_date, "
                "effective_end_date, approval_status, created_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP) "
                "ON CONFLICT (rate_id) DO NOTHING",
                (
                    r.rate_id,
                    r.timekeeper_id,
                    r.vendor_id,
                    r.rate_type,
                    r.hourly_rate,
                    r.currency_code,
                    r.effective_start_date,
                    r.effective_end_date,
                    r.approval_status,
                ),
            )
        for m in seed.matters:
            cur.execute(
                "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
                "matter_type, practice_area, matter_status, jurisdiction, risk_level, "
                "open_date, close_date, legal_entity_id, business_unit, "
                "matter_owner_user_id, budget_amount, budget_currency_code, "
                "created_at, updated_at, source_system) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s) "
                "ON CONFLICT (matter_id) DO NOTHING",
                (
                    m.matter_id,
                    m.client_matter_id,
                    m.matter_name,
                    m.matter_type,
                    m.practice_area,
                    m.matter_status,
                    m.jurisdiction,
                    m.risk_level,
                    m.open_date,
                    m.close_date,
                    m.legal_entity_id,
                    m.business_unit,
                    m.matter_owner_user_id,
                    m.budget_amount,
                    m.budget_currency_code,
                    m.source_system,
                ),
            )
        for inv in seed.invoices:
            cur.execute(
                "INSERT INTO fact_invoice (invoice_id, invoice_number, matter_id, "
                "client_matter_id, vendor_id, invoice_date, invoice_status, "
                "currency_code, invoice_total_amount, fee_total_amount, "
                "expense_total_amount, approved_amount, paid_amount, ledes_format, "
                "created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (invoice_id) DO NOTHING",
                (
                    inv.invoice_id,
                    inv.invoice_number,
                    inv.matter_id,
                    inv.client_matter_id,
                    inv.vendor_id,
                    inv.invoice_date,
                    inv.invoice_status,
                    inv.currency_code,
                    inv.invoice_total_amount,
                    inv.fee_total_amount,
                    inv.expense_total_amount,
                    inv.approved_amount,
                    inv.paid_amount,
                    inv.ledes_format,
                ),
            )
        for li in seed.line_items:
            cur.execute(
                "INSERT INTO fact_invoice_line_item (invoice_line_item_id, invoice_id, "
                "line_item_number, matter_id, client_matter_id, vendor_id, timekeeper_id, "
                "line_item_date, line_item_type, task_code, activity_code, expense_code, "
                "units, unit_rate, line_item_total_amount, currency_code, usd_amount, "
                "fx_rate_to_usd, billing_guideline_flag, created_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP) "
                "ON CONFLICT (invoice_line_item_id) DO NOTHING",
                (
                    li.invoice_line_item_id,
                    li.invoice_id,
                    li.line_item_number,
                    li.matter_id,
                    li.client_matter_id,
                    li.vendor_id,
                    li.timekeeper_id,
                    li.line_item_date,
                    li.line_item_type,
                    li.task_code,
                    li.activity_code,
                    li.expense_code,
                    li.units,
                    li.unit_rate,
                    li.line_item_total_amount,
                    li.currency_code,
                    li.usd_amount,
                    li.fx_rate_to_usd,
                    li.billing_guideline_flag,
                ),
            )
    connection.commit()
