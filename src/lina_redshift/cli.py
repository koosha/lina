"""`lina-redshift` CLI entry point — Click-based, JSON stdout, structured stderr."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import click
import psycopg2

from lina_redshift.connection import resolve_config
from lina_redshift.logging_config import configure_logging
from lina_redshift.migrations.runner import MigrationRunner, list_pending


def _migrations_sql_dir() -> Path:
    return Path(str(resources.files("lina_redshift.migrations").joinpath("sql")))


@click.group()
@click.option("--target", type=click.Choice(["postgres", "redshift"]), default="redshift")
@click.pass_context
def main(ctx: click.Context, target: str) -> None:
    configure_logging()
    ctx.ensure_object(dict)
    cfg = resolve_config(target=target)  # type: ignore[arg-type]
    ctx.obj["config"] = cfg


@main.group()
def migrate() -> None:
    """DDL migration commands."""


@migrate.command("up")
@click.pass_context
def migrate_up(ctx: click.Context) -> None:
    cfg = ctx.obj["config"]
    conn = psycopg2.connect(cfg.dsn)
    try:
        runner = MigrationRunner(connection=conn, sql_dir=_migrations_sql_dir(), target=cfg.target)
        applied = runner.apply_pending()
    finally:
        conn.close()
    click.echo(json.dumps({"applied": len(applied), "versions": applied}, indent=2))


@migrate.command("status")
@click.pass_context
def migrate_status(ctx: click.Context) -> None:
    cfg = ctx.obj["config"]
    conn = psycopg2.connect(cfg.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version varchar PRIMARY KEY, applied_at timestamp NOT NULL "
                "DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.commit()
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            applied = [r[0] for r in cur.fetchall()]
        pending = list_pending(connection=conn, sql_dir=_migrations_sql_dir())
    finally:
        conn.close()
    click.echo(json.dumps({"applied": applied, "pending": pending}, indent=2))


if __name__ == "__main__":
    main()
