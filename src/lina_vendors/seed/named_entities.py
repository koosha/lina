"""Hand-written named timekeepers for golden-path tests and cross-subsystem ID parity.

These IDs MUST match `lina_redshift.seed.named_entities.NAMED_TIMEKEEPERS`. Each
entry is enriched with OpenSearch-only fields (practice_areas, jurisdictions,
expertise_summary, ...). Rates here align with `NAMED_RATES` in C.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class NamedTimekeeper:
    timekeeper_id: str
    vendor_id: str
    vendor_name: str
    first_name: str
    last_name: str
    display_name: str
    email: str
    phone_number: str
    office_country_code: str
    office_state_province: str | None
    office_city: str
    office_postal_code: str
    bar_admissions: list[str]
    jurisdictions: list[str]
    industries: list[str]
    practice_areas: list[str]
    currency_code: str
    standard_hourly_rate: float
    effective_hourly_rate: float
    years_of_experience: int
    timekeeper_classification: str
    expertise_summary: str
    representative_matters_summary: str
    active_status: str = "active"
    source_system: str = "named_seed"
    rate_history: list[dict[str, object]] = field(default_factory=list)
    profile_sources: list[dict[str, object]] = field(default_factory=list)

    def to_doc(self) -> dict[str, object]:
        """Serialize to the OpenSearch document shape."""
        return asdict(self)


NAMED_TIMEKEEPERS: list[NamedTimekeeper] = [
    NamedTimekeeper(
        timekeeper_id="tk_walker_partner",
        vendor_id="vendor_walker",
        vendor_name="Walker & Associates LLP",
        first_name="Patricia",
        last_name="Walker",
        display_name="Patricia Walker",
        email="patricia.walker@walker-llp.example",
        phone_number="+1-415-555-0101",
        office_country_code="US",
        office_state_province="CA",
        office_city="San Francisco",
        office_postal_code="94104",
        bar_admissions=["CA", "NY"],
        jurisdictions=["US", "CA", "NY"],
        industries=["Technology", "Finance"],
        practice_areas=["Litigation", "Commercial"],
        currency_code="USD",
        standard_hourly_rate=950.0,
        effective_hourly_rate=950.0,
        years_of_experience=22,
        timekeeper_classification="Partner",
        expertise_summary=(
            "Senior trial partner specializing in complex commercial litigation, "
            "shareholder disputes, and technology-sector contract enforcement."
        ),
        representative_matters_summary=(
            "Lead trial counsel in Acme v. Beta Litigation; class-action defense for "
            "multiple Fortune 500 technology clients."
        ),
        rate_history=[
            {
                "rate_type": "standard",
                "hourly_rate": 950.0,
                "currency_code": "USD",
                "effective_start_date": "2024-01-01",
                "effective_end_date": "2024-12-31",
                "matter_id": None,
                "approval_status": "approved",
            },
            {
                "rate_type": "standard",
                "hourly_rate": 995.0,
                "currency_code": "USD",
                "effective_start_date": "2025-01-01",
                "effective_end_date": None,
                "matter_id": None,
                "approval_status": "approved",
            },
        ],
        profile_sources=[
            {
                "source_name": "vendor_self_report",
                "source_record_id": "walker_self_2024",
                "last_synced_at": "2024-12-15T00:00:00Z",
            }
        ],
    ),
    NamedTimekeeper(
        timekeeper_id="tk_walker_associate",
        vendor_id="vendor_walker",
        vendor_name="Walker & Associates LLP",
        first_name="Roy",
        last_name="Sanchez",
        display_name="Roy Sanchez",
        email="roy.sanchez@walker-llp.example",
        phone_number="+1-415-555-0102",
        office_country_code="US",
        office_state_province="CA",
        office_city="San Francisco",
        office_postal_code="94104",
        bar_admissions=["CA"],
        jurisdictions=["US", "CA"],
        industries=["Technology"],
        practice_areas=["Litigation", "Employment"],
        currency_code="USD",
        standard_hourly_rate=525.0,
        effective_hourly_rate=525.0,
        years_of_experience=5,
        timekeeper_classification="Associate",
        expertise_summary=(
            "Mid-level associate handling discovery, motion practice, and depositions "
            "across commercial litigation and employment matters."
        ),
        representative_matters_summary=(
            "Discovery lead on Acme v. Beta Litigation; second chair on regional "
            "employment defense matters."
        ),
        rate_history=[
            {
                "rate_type": "standard",
                "hourly_rate": 525.0,
                "currency_code": "USD",
                "effective_start_date": "2024-01-01",
                "effective_end_date": None,
                "matter_id": None,
                "approval_status": "approved",
            }
        ],
        profile_sources=[
            {
                "source_name": "vendor_self_report",
                "source_record_id": "walker_self_2024",
                "last_synced_at": "2024-12-15T00:00:00Z",
            }
        ],
    ),
    NamedTimekeeper(
        timekeeper_id="tk_jones_partner",
        vendor_id="vendor_jones",
        vendor_name="Jones Privacy Law",
        first_name="Daniel",
        last_name="Jones",
        display_name="Daniel Jones",
        email="daniel.jones@jonesprivacy.example",
        phone_number="+1-202-555-0110",
        office_country_code="US",
        office_state_province="DC",
        office_city="Washington",
        office_postal_code="20001",
        bar_admissions=["DC", "VA"],
        jurisdictions=["US", "DC", "VA"],
        industries=["Healthcare", "Technology"],
        practice_areas=["Privacy", "Data Protection", "Cybersecurity"],
        currency_code="USD",
        standard_hourly_rate=750.0,
        effective_hourly_rate=750.0,
        years_of_experience=18,
        timekeeper_classification="Partner",
        expertise_summary=(
            "Privacy and cybersecurity partner focused on US federal and state privacy "
            "regimes (HIPAA, CCPA), incident response, and regulator engagement."
        ),
        representative_matters_summary=(
            "Lead counsel for the Acme Privacy Program Review; advised on multiple "
            "major data-incident remediation programs."
        ),
        rate_history=[
            {
                "rate_type": "discounted",
                "hourly_rate": 750.0,
                "currency_code": "USD",
                "effective_start_date": "2024-01-01",
                "effective_end_date": None,
                "matter_id": None,
                "approval_status": "approved",
            }
        ],
        profile_sources=[
            {
                "source_name": "vendor_self_report",
                "source_record_id": "jones_self_2024",
                "last_synced_at": "2024-11-30T00:00:00Z",
            }
        ],
    ),
    NamedTimekeeper(
        timekeeper_id="tk_meridian_partner",
        vendor_id="vendor_meridian",
        vendor_name="Meridian Counsel UK",
        first_name="Imogen",
        last_name="Hart",
        display_name="Imogen Hart",
        email="imogen.hart@meridiancounsel.example",
        phone_number="+44-20-7946-0123",
        office_country_code="GB",
        office_state_province=None,
        office_city="London",
        office_postal_code="EC4A 1DE",
        bar_admissions=["England & Wales"],
        jurisdictions=["GB", "EU"],
        industries=["Financial Services", "Energy"],
        practice_areas=["Commercial", "Regulatory", "Compliance"],
        currency_code="GBP",
        standard_hourly_rate=780.0,
        effective_hourly_rate=780.0,
        years_of_experience=25,
        timekeeper_classification="Partner",
        expertise_summary=(
            "London-based commercial and regulatory partner advising multinationals on "
            "cross-border transactions, financial-services regulation, and post-Brexit "
            "compliance."
        ),
        representative_matters_summary=(
            "Trusted advisor for Acme Corp UK Ltd. on regulatory inquiries and "
            "cross-border commercial disputes."
        ),
        rate_history=[
            {
                "rate_type": "standard",
                "hourly_rate": 780.0,
                "currency_code": "GBP",
                "effective_start_date": "2024-01-01",
                "effective_end_date": None,
                "matter_id": None,
                "approval_status": "approved",
            }
        ],
        profile_sources=[
            {
                "source_name": "vendor_self_report",
                "source_record_id": "meridian_self_2024",
                "last_synced_at": "2024-12-01T00:00:00Z",
            }
        ],
    ),
    NamedTimekeeper(
        timekeeper_id="tk_meridian_paralegal",
        vendor_id="vendor_meridian",
        vendor_name="Meridian Counsel UK",
        first_name="Oliver",
        last_name="Reed",
        display_name="Oliver Reed",
        email="oliver.reed@meridiancounsel.example",
        phone_number="+44-20-7946-0124",
        office_country_code="GB",
        office_state_province=None,
        office_city="London",
        office_postal_code="EC4A 1DE",
        bar_admissions=[],
        jurisdictions=["GB"],
        industries=["Financial Services"],
        practice_areas=["Litigation Support", "Document Review"],
        currency_code="GBP",
        standard_hourly_rate=220.0,
        effective_hourly_rate=220.0,
        years_of_experience=8,
        timekeeper_classification="Paralegal",
        expertise_summary=(
            "Senior paralegal supporting commercial litigation and regulatory work — "
            "document review, e-discovery coordination, and bundle preparation."
        ),
        representative_matters_summary=(
            "Document-review lead on multiple cross-border disputes for Acme Corp UK Ltd."
        ),
        rate_history=[
            {
                "rate_type": "standard",
                "hourly_rate": 220.0,
                "currency_code": "GBP",
                "effective_start_date": "2024-01-01",
                "effective_end_date": None,
                "matter_id": None,
                "approval_status": "approved",
            }
        ],
        profile_sources=[
            {
                "source_name": "vendor_self_report",
                "source_record_id": "meridian_self_2024",
                "last_synced_at": "2024-12-01T00:00:00Z",
            }
        ],
    ),
]


def named_timekeeper_docs() -> list[dict[str, object]]:
    """Return all named timekeepers as OpenSearch document dicts."""
    return [t.to_doc() for t in NAMED_TIMEKEEPERS]
