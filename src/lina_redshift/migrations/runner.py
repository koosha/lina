"""Apply numbered .sql migration files in order, recording version state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.dialect import translate_for_postgres

Target = Literal["postgres", "redshift"]

_MIGRATIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version varchar PRIMARY KEY,
    applied_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


@dataclass
class MigrationRunner:
    connection: PgConnection
    sql_dir: Path
    target: Target

    def apply_pending(self) -> list[str]:
        applied: list[str] = []
        self._ensure_migrations_table()
        already = self._already_applied()
        for path in sorted(self.sql_dir.glob("*.sql")):
            version = path.stem
            if version in already:
                continue
            sql = path.read_text()
            if self.target == "postgres":
                sql = translate_for_postgres(sql)
            self._execute_migration(version=version, sql=sql)
            applied.append(version)
        return applied

    def _ensure_migrations_table(self) -> None:
        with self.connection.cursor() as cur:
            cur.execute(_MIGRATIONS_TABLE_DDL)
        self.connection.commit()

    def _already_applied(self) -> set[str]:
        with self.connection.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations")
            return {row[0] for row in cur.fetchall()}

    def _execute_migration(self, *, version: str, sql: str) -> None:
        with self.connection.cursor() as cur:
            if self.target == "postgres":
                cur.execute(sql)
            else:
                # Redshift: split on top-level ';' and run statements individually,
                # since some Redshift DDL does not support transactions.
                for statement in _split_statements(sql):
                    if statement.strip():
                        cur.execute(statement)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
        self.connection.commit()


def _split_statements(sql: str) -> list[str]:
    """Split SQL on top-level semicolons. Naive but sufficient for our DDL files."""
    out: list[str] = []
    buf: list[str] = []
    paren_depth = 0
    in_single = False
    for ch in sql:
        if ch == "'" and not in_single:
            in_single = True
        elif ch == "'" and in_single:
            in_single = False
        elif not in_single:
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1
            elif ch == ";" and paren_depth == 0:
                out.append("".join(buf))
                buf = []
                continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def list_pending(*, connection: PgConnection, sql_dir: Path) -> list[str]:
    with connection.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        already = {row[0] for row in cur.fetchall()}
    return [p.stem for p in sorted(sql_dir.glob("*.sql")) if p.stem not in already]
