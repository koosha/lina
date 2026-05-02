"""Connection factory for Postgres (dev/unit) and Redshift (integration/prod)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Literal

import psycopg2
from psycopg2.extensions import connection as PgConnection  # noqa: N812

Target = Literal["postgres", "redshift"]


class MissingDsnError(RuntimeError):
    """Raised when the required DSN environment variable is unset."""


@dataclass(frozen=True)
class ConnectionConfig:
    dsn: str
    target: Target
    statement_timeout_ms: int = 30_000

    def env_var_name(self) -> str:
        return "LINA_REDSHIFT_DSN" if self.target == "redshift" else "LINA_POSTGRES_DSN"


def resolve_config(target: Target = "redshift") -> ConnectionConfig:
    env_name = "LINA_REDSHIFT_DSN" if target == "redshift" else "LINA_POSTGRES_DSN"
    dsn = os.environ.get(env_name)
    if not dsn:
        raise MissingDsnError(f"{env_name} is not set. Export it before invoking lina-redshift.")
    timeout_str = os.environ.get("LINA_STATEMENT_TIMEOUT_MS", "30000")
    return ConnectionConfig(dsn=dsn, target=target, statement_timeout_ms=int(timeout_str))


@contextmanager
def open_connection(config: ConnectionConfig, *, read_only: bool = True) -> Iterator[PgConnection]:
    """Open a connection with read-only and statement-timeout GUCs applied."""
    conn = psycopg2.connect(config.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (config.statement_timeout_ms,))
            if read_only:
                cur.execute("SET default_transaction_read_only = on")
                cur.execute("SET transaction_read_only = on")
        yield conn
    finally:
        conn.close()
