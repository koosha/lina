"""Bootstrap the read-only Redshift runtime user used by the chat Lambda.

The chat path doesn't need any DDL/DML privileges. Running as the
admin role gives it the full keys to the warehouse — a meaningful
risk even on a sandbox. This module creates a dedicated
``lina_app_readonly`` role with USAGE + SELECT only, and (optionally)
puts the generated password into a Secrets Manager secret so the
Lambda can pick it up at cold start.

Designed to be idempotent: re-running the bootstrap rotates the
password and re-applies the grants, which is exactly what an operator
wants for a "the secret leaked, rotate it" workflow.
"""

from __future__ import annotations

import json
import secrets
import string
from dataclasses import dataclass
from typing import Any

# Deliberately narrow alphabet — Redshift accepts a wider set, but
# excluding shell-special chars keeps the password safe to copy/paste
# from a runbook step into AWS CLI without escape headaches.
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "-_"
_PASSWORD_LENGTH = 32

RUNTIME_USERNAME = "lina_app_readonly"


@dataclass(frozen=True)
class BootstrapResult:
    """Outcome of a single bootstrap run.

    The password is included so the operator (or a wrapping script) can
    do anything with it that ``--put-secret-arn`` doesn't already cover.
    """

    username: str
    password: str
    granted_tables: int
    secret_arn: str | None
    secret_version_id: str | None


def generate_password() -> str:
    """Return a fresh random password using only safe-to-shell-copy chars."""
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH))


def bootstrap_runtime_user(
    *,
    admin_conn: Any,
    schema: str = "public",
    password: str | None = None,
    secrets_client: Any | None = None,
    put_secret_arn: str | None = None,
) -> BootstrapResult:
    """Create or re-create ``lina_app_readonly`` with read-only grants.

    Sequence (all on a single transaction the caller commits):
      1. DROP USER IF EXISTS to make the call idempotent.
      2. CREATE USER with the new password.
      3. GRANT USAGE on the schema.
      4. GRANT SELECT on every existing table/view in the schema.
      5. ALTER DEFAULT PRIVILEGES so future tables created by the
         admin role auto-grant SELECT to the runtime user. (Without
         this, every new migration would need a follow-up grant step.)

    If ``put_secret_arn`` is provided, the password is also written to
    that Secrets Manager secret as a JSON envelope so the Lambda can
    consume it via the same ``json.loads(SecretString)["password"]``
    pattern it already uses for the admin secret.
    """
    if password is None:
        password = generate_password()

    granted_count = 0
    with admin_conn.cursor() as cur:
        cur.execute(f"DROP USER IF EXISTS {RUNTIME_USERNAME}")
        # `CREATE USER` doesn't take a placeholder for the password — it
        # has to be a literal in the statement. The bootstrap path runs
        # only via operator CLI, never inside a Lambda response loop,
        # and the password is freshly generated, so no SQL-injection
        # surface exists. We still escape any single-quote.
        escaped = password.replace("'", "''")
        cur.execute(f"CREATE USER {RUNTIME_USERNAME} PASSWORD '{escaped}'")
        cur.execute(f"GRANT USAGE ON SCHEMA {schema} TO {RUNTIME_USERNAME}")
        cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {RUNTIME_USERNAME}")
        cur.execute(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} "
            f"GRANT SELECT ON TABLES TO {RUNTIME_USERNAME}"
        )
        cur.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = %s",
            (schema,),
        )
        row = cur.fetchone()
        granted_count = int(row[0]) if row else 0
    admin_conn.commit()

    secret_version_id: str | None = None
    if put_secret_arn:
        if secrets_client is None:
            raise ValueError("put_secret_arn requires secrets_client")
        resp = secrets_client.put_secret_value(
            SecretId=put_secret_arn,
            SecretString=json.dumps(
                {
                    "username": RUNTIME_USERNAME,
                    "password": password,
                }
            ),
        )
        secret_version_id = resp.get("VersionId")

    return BootstrapResult(
        username=RUNTIME_USERNAME,
        password=password,
        granted_tables=granted_count,
        secret_arn=put_secret_arn,
        secret_version_id=secret_version_id,
    )


__all__ = [
    "RUNTIME_USERNAME",
    "BootstrapResult",
    "bootstrap_runtime_user",
    "generate_password",
]
