"""Hardcoded subset of UTBMS task/activity/expense codes."""

from __future__ import annotations

from dataclasses import dataclass

from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.seed import _on_conflict_clause


@dataclass(frozen=True)
class BillingCode:
    billing_code_id: str
    code: str
    code_type: str  # "task" | "activity" | "expense"
    code_set: str  # "UTBMS"
    description: str


_TASK_CODES: list[BillingCode] = [
    BillingCode(f"bc_task_{c}", c, "task", "UTBMS", desc)
    for c, desc in [
        ("L100", "Case Assessment, Development and Administration"),
        ("L110", "Fact Investigation/Development"),
        ("L120", "Analysis/Strategy"),
        ("L130", "Experts/Consultants"),
        ("L140", "Document/File Management"),
        ("L150", "Budgeting"),
        ("L160", "Settlement/Non-Binding ADR"),
        ("L190", "Other Case Assessment"),
        ("L200", "Pre-Trial Pleadings and Motions"),
        ("L210", "Pleadings"),
        ("L220", "Preliminary Injunctions/Provisional Remedies"),
        ("L230", "Court Mandated Conferences"),
        ("L240", "Dispositive Motions"),
        ("L250", "Other Written Motions and Submissions"),
        ("L300", "Discovery"),
        ("L310", "Written Discovery"),
        ("L320", "Document Production"),
        ("L330", "Depositions"),
        ("L340", "Expert Discovery"),
        ("L350", "Discovery Motions"),
        ("L400", "Trial Preparation and Trial"),
        ("L410", "Fact Witnesses"),
        ("L420", "Expert Witnesses"),
        ("L430", "Written Motions and Submissions"),
        ("L440", "Other Trial Preparation"),
    ]
]

_ACTIVITY_CODES: list[BillingCode] = [
    BillingCode(f"bc_activity_{c}", c, "activity", "UTBMS", desc)
    for c, desc in [
        ("A101", "Plan and prepare for"),
        ("A102", "Research"),
        ("A103", "Draft/revise"),
        ("A104", "Review/analyze"),
        ("A105", "Communicate (in firm)"),
        ("A106", "Communicate (with client)"),
        ("A107", "Communicate (other outside counsel)"),
        ("A108", "Communicate (other external)"),
        ("A109", "Appear for/attend"),
        ("A110", "Manage data/files"),
    ]
]

_EXPENSE_CODES: list[BillingCode] = [
    BillingCode(f"bc_expense_{c}", c, "expense", "UTBMS", desc)
    for c, desc in [
        ("E101", "Copying"),
        ("E102", "Outside printing"),
        ("E103", "Word processing"),
        ("E104", "Facsimile"),
        ("E105", "Telephone"),
        ("E106", "Online research"),
        ("E107", "Delivery services/messengers"),
        ("E108", "Postage"),
        ("E109", "Local travel"),
        ("E110", "Out-of-town travel"),
        ("E111", "Meals"),
        ("E112", "Court fees"),
        ("E113", "Subpoena fees"),
        ("E114", "Witness fees"),
        ("E115", "Deposition transcripts"),
    ]
]

BILLING_CODES: list[BillingCode] = [*_TASK_CODES, *_ACTIVITY_CODES, *_EXPENSE_CODES]


def load_billing_codes(connection: PgConnection) -> None:
    """Insert billing codes idempotently via UPSERT-style ON CONFLICT."""
    on_conflict = _on_conflict_clause(connection, "billing_code_id")
    with connection.cursor() as cur:
        for c in BILLING_CODES:
            cur.execute(
                "INSERT INTO dim_billing_code (billing_code_id, code, code_type, "
                "code_set, description, active_status, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                f"{on_conflict}",
                (c.billing_code_id, c.code, c.code_type, c.code_set, c.description),
            )
    connection.commit()
