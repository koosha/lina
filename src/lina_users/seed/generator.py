"""Deterministic Faker-driven generator for bulk OpenSearch user docs."""

from __future__ import annotations

import random

from faker import Faker

_DEPARTMENTS = ["Legal", "HR", "Engineering", "Finance", "Procurement", "Marketing", "Sales"]
_BUSINESS_UNITS = ["Enterprise", "Product", "EMEA", "APAC", "Platform"]
_REGIONS_TO_COUNTRY = {
    "AMER": "US",
    "EMEA": "GB",
    "APAC": "JP",
}
_TIMEZONES = {
    "AMER": "America/New_York",
    "EMEA": "Europe/London",
    "APAC": "Asia/Tokyo",
}
_USER_STATUSES = ["active", "active", "active", "inactive"]
_ROLE_POOL = [
    "business_user",
    "matter_owner",
    "legal_ops",
    "hr_ops",
    "inhouse_counsel",
    "compliance_ops",
    "procurement",
    "paralegal",
]


def generate_users(*, count: int = 50, seed: int = 42) -> list[dict[str, object]]:
    """Return `count` user docs with deterministic IDs `user_gen_000...user_gen_<count-1>`."""
    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)  # noqa: S311 — deterministic test fixture, not crypto

    users: list[dict[str, object]] = []
    for i in range(count):
        first = fake.first_name()
        last = fake.last_name()
        region = rng.choice(list(_REGIONS_TO_COUNTRY.keys()))
        country = _REGIONS_TO_COUNTRY[region]
        timezone = _TIMEZONES[region]
        department = rng.choice(_DEPARTMENTS)
        business_unit = rng.choice(_BUSINESS_UNITS)
        roles = rng.sample(_ROLE_POOL, k=rng.randint(1, 3))
        user_id = f"user_gen_{i:03d}"
        email = f"{first.lower()}.{last.lower()}.{i:03d}@acmegen.example"
        users.append(
            {
                "user_id": user_id,
                "employee_id": f"G{i:05d}",
                "email": email,
                "email_text": email,
                "first_name": first,
                "last_name": last,
                "display_name": f"{first} {last}",
                "job_title": fake.job(),
                "department": department,
                "business_unit": business_unit,
                "cost_center": "cc_eng_platform" if department == "Engineering" else "cc_legal_ops",
                "manager_user_id": None,
                "region": region,
                "country_code": country,
                "timezone": timezone,
                "user_status": rng.choice(_USER_STATUSES),
                "user_type": "employee",
                "roles": roles,
                "permission_tags": [],
                "legal_team_role": None,
                "practice_area_focus": [],
                "source_system": "bulk_generator",
            }
        )
    return users
