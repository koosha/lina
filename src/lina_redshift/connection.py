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


def apply_session_settings(
    conn: PgConnection,
    *,
    statement_timeout_ms: int = 30_000,
    read_only: bool = True,
) -> None:
    """Apply Lina's runtime session GUCs to a freshly-opened connection.

    Used by both the CLI (DSN path, via ``open_connection``) and the Lambda
    (keyword-args path) so the chat runtime always has the same statement
    timeout and read-only posture regardless of how the connection was
    opened.
    """
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = %s", (statement_timeout_ms,))
        if read_only:
            cur.execute("SET default_transaction_read_only = on")
            cur.execute("SET transaction_read_only = on")


def connect_with_kwargs(
    *,
    host: str,
    port: int,
    dbname: str,
    user: str,
    password: str,
    connect_timeout: int = 5,
    statement_timeout_ms: int = 30_000,
    read_only: bool = True,
) -> PgConnection:
    """Open a runtime connection from explicit fields, applying Lina settings.

    Prefer this over building a ``postgresql://...`` DSN by string
    interpolation: f-string interpolation breaks if the password contains
    URL-sensitive characters (``@``, ``/``, ``:``, ``#``, ``%`` …) and
    psycopg2 would silently misparse the host.

    Caller is responsible for closing the connection.
    """
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        connect_timeout=connect_timeout,
    )
    try:
        apply_session_settings(
            conn, statement_timeout_ms=statement_timeout_ms, read_only=read_only
        )
    except Exception:
        conn.close()
        raise
    return conn


@contextmanager
def open_connection(config: ConnectionConfig, *, read_only: bool = True) -> Iterator[PgConnection]:
    """Open a connection with read-only and statement-timeout GUCs applied."""
    conn = psycopg2.connect(config.dsn)
    try:
        apply_session_settings(
            conn,
            statement_timeout_ms=config.statement_timeout_ms,
            read_only=read_only,
        )
        yield conn
    finally:
        conn.close()
