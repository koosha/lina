"""Unit tests for the migration runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection  # noqa: N812

from lina_redshift.migrations.runner import (
    MigrationRunner,
    list_pending,
)


@pytest.fixture
def sql_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sql"
    d.mkdir()
    (d / "001_first.sql").write_text("CREATE TABLE thing_one (id varchar PRIMARY KEY);")
    (d / "002_second.sql").write_text(
        "CREATE TABLE thing_two (id varchar PRIMARY KEY, ref varchar);"
    )
    return d


@pytest.mark.unit
def test_apply_pending_creates_migrations_table(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")

    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT version FROM schema_migrations ORDER BY version",
        )
        rows = [r[0] for r in cur.fetchall()]
    assert rows == ["001_first", "002_second"]


@pytest.mark.unit
def test_apply_pending_creates_target_tables(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")

    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'thing_%' ORDER BY table_name"
        )
        rows = [r[0] for r in cur.fetchall()]
    assert rows == ["thing_one", "thing_two"]


@pytest.mark.unit
def test_apply_pending_is_idempotent(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")
    runner.apply_pending()

    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM schema_migrations")
        assert cur.fetchone()[0] == 2


@pytest.mark.unit
def test_apply_pending_applies_only_new_files(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")
    runner.apply_pending()

    (sql_dir / "003_third.sql").write_text(
        "CREATE TABLE thing_three (id varchar PRIMARY KEY);"
    )
    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations ORDER BY version")
        rows = [r[0] for r in cur.fetchall()]
    assert rows == ["001_first", "002_second", "003_third"]


@pytest.mark.unit
def test_list_pending_returns_unapplied(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")
    runner.apply_pending()
    (sql_dir / "003_third.sql").write_text("CREATE TABLE thing_three (id varchar);")

    pending = list_pending(connection=pg_conn, sql_dir=sql_dir)

    assert pending == ["003_third"]


@pytest.mark.unit
def test_apply_pending_translates_redshift_dialect_for_postgres(
    pg_conn: PgConnection, tmp_path: Path,
) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_redshift.sql").write_text(
        "CREATE TABLE rs_thing (id varchar PRIMARY KEY, note varchar(max)) "
        "DISTSTYLE AUTO SORTKEY AUTO;"
    )
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")

    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'rs_thing' ORDER BY column_name"
        )
        rows = cur.fetchall()
    assert rows == [("id", "character varying"), ("note", "character varying")]
