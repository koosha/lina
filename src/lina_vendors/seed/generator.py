"""Deterministic Faker-driven generator for bulk OpenSearch vendor lawyer docs."""

from __future__ import annotations

import random

from faker import Faker

_PRACTICE_AREA_POOL = [
    "Litigation",
    "Commercial",
    "Privacy",
    "Employment",
    "Tax",
    "IP",
    "Patents",
    "Regulatory",
    "Compliance",
    "M&A",
    "Real Estate",
    "Bankruptcy",
]

_INDUSTRY_POOL = [
    "Technology",
    "Finance",
    "Healthcare",
    "Energy",
    "Retail",
    "Manufacturing",
    "Media",
    "Biotech",
]

_BAR_BY_COUNTRY = {
    "US": ["NY", "CA", "TX", "IL", "DC", "MA"],
    "GB": ["England & Wales"],
    "DE": ["Berlin", "Munich"],
}

_COUNTRY_POOL = ["US", "GB", "DE"]

_CURRENCY_BY_COUNTRY = {"US": "USD", "GB": "GBP", "DE": "EUR"}

_CITY_BY_COUNTRY = {
    "US": ["New York", "San Francisco", "Chicago", "Boston", "Washington"],
    "GB": ["London", "Manchester", "Edinburgh"],
    "DE": ["Berlin", "Munich", "Frankfurt"],
}

_CLASSIFICATIONS = [
    "Partner",
    "Counsel",
    "Senior Associate",
    "Associate",
    "Paralegal",
]

_ACTIVE_STATUSES = ["active", "active", "active", "inactive"]


def generate_timekeepers(*, count: int = 200, seed: int = 42) -> list[dict[str, object]]:
    """Return `count` timekeeper docs with deterministic IDs `tk_b_gen_000...tk_b_gen_<count-1>`.

    `vendor_id` is one of `vendor_b_gen_000` ... `vendor_b_gen_009` (10 generated vendors).
    These IDs are deliberately disjoint from C's `tk_gen_*` / `vendor_gen_*` namespace.
    """
    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)  # noqa: S311 — deterministic test fixture, not crypto

    # Build a stable map of generated vendor_id -> (vendor_name, country, currency)
    vendor_count = 10
    vendor_specs: list[tuple[str, str, str, str]] = []
    for v in range(vendor_count):
        country = rng.choice(_COUNTRY_POOL)
        currency = _CURRENCY_BY_COUNTRY[country]
        vendor_id = f"vendor_b_gen_{v:03d}"
        vendor_name = (
            f"{fake.last_name()} & {fake.last_name()} {rng.choice(['LLP', 'Law', 'Counsel'])}"
        )
        vendor_specs.append((vendor_id, vendor_name, country, currency))

    docs: list[dict[str, object]] = []
    for i in range(count):
        vendor_id, vendor_name, country, currency = vendor_specs[i % vendor_count]
        first = fake.first_name()
        last = fake.last_name()
        classification = rng.choice(_CLASSIFICATIONS)
        # Plausible rate ranges anchored to classification
        if classification == "Partner":
            base_rate = float(rng.randint(700, 1200))
        elif classification == "Counsel":
            base_rate = float(rng.randint(550, 850))
        elif classification == "Senior Associate":
            base_rate = float(rng.randint(450, 700))
        elif classification == "Associate":
            base_rate = float(rng.randint(300, 550))
        else:  # Paralegal
            base_rate = float(rng.randint(150, 280))
        years = rng.randint(15, 35) if classification == "Partner" else rng.randint(1, 12)
        bars = rng.sample(_BAR_BY_COUNTRY[country], k=min(2, len(_BAR_BY_COUNTRY[country])))
        practice_areas = rng.sample(_PRACTICE_AREA_POOL, k=rng.randint(1, 3))
        industries = rng.sample(_INDUSTRY_POOL, k=rng.randint(1, 2))
        timekeeper_id = f"tk_b_gen_{i:03d}"
        email = f"{first.lower()}.{last.lower()}.{i:03d}@vendorgen.example"
        docs.append(
            {
                "timekeeper_id": timekeeper_id,
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "first_name": first,
                "last_name": last,
                "display_name": f"{first} {last}",
                "email": email,
                "phone_number": fake.numerify("+1-###-555-####"),
                "office_country_code": country,
                "office_state_province": None,
                "office_city": rng.choice(_CITY_BY_COUNTRY[country]),
                "office_postal_code": fake.postcode(),
                "bar_admissions": bars,
                "jurisdictions": [country],
                "industries": industries,
                "practice_areas": practice_areas,
                "currency_code": currency,
                "standard_hourly_rate": base_rate,
                "effective_hourly_rate": base_rate,
                "years_of_experience": years,
                "timekeeper_classification": classification,
                "active_status": rng.choice(_ACTIVE_STATUSES),
                "expertise_summary": fake.paragraph(nb_sentences=2),
                "representative_matters_summary": fake.paragraph(nb_sentences=1),
                "rate_history": [
                    {
                        "rate_type": "standard",
                        "hourly_rate": base_rate,
                        "currency_code": currency,
                        "effective_start_date": "2024-01-01",
                        "effective_end_date": None,
                        "matter_id": None,
                        "approval_status": "approved",
                    }
                ],
                "profile_sources": [
                    {
                        "source_name": "bulk_generator",
                        "source_record_id": f"gen_{i:05d}",
                        "last_synced_at": "2024-12-31T00:00:00Z",
                    }
                ],
                "source_system": "bulk_generator",
            }
        )
    return docs
