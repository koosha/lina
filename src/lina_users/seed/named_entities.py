"""Hand-written named users for golden-path tests and cross-subsystem ID parity.

The IDs `user_jane_smith` and `user_alex_lee` MUST match the
`matter_owner_user_id` values referenced in `lina_redshift.seed.named_entities`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class NamedUser:
    user_id: str
    employee_id: str
    email: str
    first_name: str
    last_name: str
    display_name: str
    job_title: str
    department: str
    business_unit: str
    cost_center: str
    manager_user_id: str | None
    region: str
    country_code: str
    timezone: str
    user_status: str = "active"
    user_type: str = "employee"
    legal_team_role: str | None = None
    practice_area_focus: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    permission_tags: list[str] = field(default_factory=list)
    source_system: str = "named_seed"

    def to_doc(self) -> dict[str, object]:
        """Serialize to the OpenSearch document shape (with `email_text` mirror)."""
        doc = asdict(self)
        doc["email_text"] = self.email
        return doc


NAMED_USERS: list[NamedUser] = [
    NamedUser(
        user_id="user_sam_rodriguez",
        employee_id="E1001",
        email="sam.rodriguez@acme.com",
        first_name="Samantha",
        last_name="Rodriguez",
        display_name="Sam Rodriguez",
        job_title="VP, Legal Operations",
        department="Legal",
        business_unit="Enterprise",
        cost_center="cc_legal_ops",
        manager_user_id=None,
        region="AMER",
        country_code="US",
        timezone="America/Los_Angeles",
        legal_team_role="ops_lead",
        practice_area_focus=["Operations"],
        roles=["legal_ops", "matter_owner"],
        permission_tags=["matter_owner", "approver"],
    ),
    NamedUser(
        user_id="user_jane_smith",
        employee_id="E1002",
        email="jane.smith@acme.com",
        first_name="Jane",
        last_name="Smith",
        display_name="Jane Smith",
        job_title="Senior Counsel, Litigation",
        department="Legal",
        business_unit="Enterprise",
        cost_center="cc_legal_ops",
        manager_user_id="user_sam_rodriguez",
        region="AMER",
        country_code="US",
        timezone="America/New_York",
        legal_team_role="senior_counsel",
        practice_area_focus=["Litigation", "Employment"],
        roles=["matter_owner", "inhouse_counsel"],
        permission_tags=["matter_owner"],
    ),
    NamedUser(
        user_id="user_alex_lee",
        employee_id="E1003",
        email="alex.lee@acme.com",
        first_name="Alex",
        last_name="Lee",
        display_name="Alex Lee",
        job_title="Privacy Counsel",
        department="Legal",
        business_unit="Product",
        cost_center="cc_legal_ops",
        manager_user_id="user_sam_rodriguez",
        region="AMER",
        country_code="US",
        timezone="America/Los_Angeles",
        legal_team_role="counsel",
        practice_area_focus=["Privacy"],
        roles=["matter_owner", "inhouse_counsel"],
        permission_tags=["matter_owner", "privacy_reviewer"],
    ),
    NamedUser(
        user_id="user_taylor_kim",
        employee_id="E1004",
        email="taylor.kim@acme.com",
        first_name="Taylor",
        last_name="Kim",
        display_name="Taylor Kim",
        job_title="Procurement Operations Lead",
        department="Procurement",
        business_unit="Enterprise",
        cost_center="cc_legal_ops",
        manager_user_id="user_sam_rodriguez",
        region="AMER",
        country_code="US",
        timezone="America/Chicago",
        legal_team_role=None,
        practice_area_focus=[],
        roles=["legal_ops", "procurement"],
        permission_tags=["vendor_reviewer"],
    ),
    NamedUser(
        user_id="user_pat_brown",
        employee_id="E1005",
        email="pat.brown@acme.com",
        first_name="Pat",
        last_name="Brown",
        display_name="Pat Brown",
        job_title="Senior Paralegal",
        department="Legal",
        business_unit="Enterprise",
        cost_center="cc_legal_ops",
        manager_user_id="user_jane_smith",
        region="AMER",
        country_code="US",
        timezone="America/New_York",
        legal_team_role="paralegal",
        practice_area_focus=["Litigation"],
        roles=["paralegal"],
        permission_tags=[],
    ),
    NamedUser(
        user_id="user_jordan_chen",
        employee_id="E1006",
        email="jordan.chen@acme.com",
        first_name="Jordan",
        last_name="Chen",
        display_name="Jordan Chen",
        job_title="HR Business Partner",
        department="HR",
        business_unit="Enterprise",
        cost_center="cc_legal_ops",
        manager_user_id=None,
        region="AMER",
        country_code="US",
        timezone="America/Los_Angeles",
        legal_team_role=None,
        practice_area_focus=[],
        roles=["hr_ops"],
        permission_tags=[],
    ),
    NamedUser(
        user_id="user_morgan_white",
        employee_id="E1007",
        email="morgan.white@acmeuk.com",
        first_name="Morgan",
        last_name="White",
        display_name="Morgan White",
        job_title="UK Legal Counsel",
        department="Legal",
        business_unit="EMEA",
        cost_center="cc_legal_ops",
        manager_user_id="user_sam_rodriguez",
        region="EMEA",
        country_code="GB",
        timezone="Europe/London",
        legal_team_role="counsel",
        practice_area_focus=["Commercial"],
        roles=["inhouse_counsel"],
        permission_tags=[],
    ),
    NamedUser(
        user_id="user_riley_garcia",
        employee_id="E1008",
        email="riley.garcia@acmede.com",
        first_name="Riley",
        last_name="Garcia",
        display_name="Riley Garcia",
        job_title="Compliance Manager",
        department="Compliance",
        business_unit="EMEA",
        cost_center="cc_legal_ops",
        manager_user_id="user_morgan_white",
        region="EMEA",
        country_code="DE",
        timezone="Europe/Berlin",
        legal_team_role="compliance",
        practice_area_focus=["Privacy", "Compliance"],
        roles=["compliance_ops"],
        permission_tags=["privacy_reviewer"],
    ),
    NamedUser(
        user_id="user_avery_hsu",
        employee_id="E1009",
        email="avery.hsu@acme.com",
        first_name="Avery",
        last_name="Hsu",
        display_name="Avery Hsu",
        job_title="Engineering Director",
        department="Engineering",
        business_unit="Product",
        cost_center="cc_eng_platform",
        manager_user_id=None,
        region="AMER",
        country_code="US",
        timezone="America/Los_Angeles",
        legal_team_role=None,
        practice_area_focus=[],
        roles=["business_user"],
        permission_tags=[],
    ),
    NamedUser(
        user_id="user_quinn_obrien",
        employee_id="E1010",
        email="quinn.obrien@acme.com",
        first_name="Quinn",
        last_name="O'Brien",
        display_name="Quinn O'Brien",
        job_title="Junior Counsel",
        department="Legal",
        business_unit="Enterprise",
        cost_center="cc_legal_ops",
        manager_user_id="user_jane_smith",
        region="AMER",
        country_code="US",
        timezone="America/New_York",
        legal_team_role="counsel",
        practice_area_focus=["Employment"],
        roles=["inhouse_counsel"],
        permission_tags=[],
        user_status="inactive",
    ),
]


def named_user_docs() -> list[dict[str, object]]:
    """Return all named users as OpenSearch document dicts."""
    return [u.to_doc() for u in NAMED_USERS]
