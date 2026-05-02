"""Unit tests for `lina-redshift migrate` commands."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from lina_redshift.cli import main


@pytest.mark.unit
def test_migrate_status_lists_pending(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", pg_dsn)
    runner = CliRunner()

    result = runner.invoke(main, ["--target", "postgres", "migrate", "status"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "pending" in payload
    assert len(payload["pending"]) == 18  # 18 migration files


@pytest.mark.unit
def test_migrate_up_applies_all(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", pg_dsn)
    runner = CliRunner()

    result = runner.invoke(main, ["--target", "postgres", "migrate", "up"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["applied"] == 18

    follow = runner.invoke(main, ["--target", "postgres", "migrate", "status"])
    follow_payload = json.loads(follow.output)
    assert follow_payload["pending"] == []


@pytest.mark.unit
def test_migrate_up_idempotent(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", pg_dsn)
    runner = CliRunner()
    runner.invoke(main, ["--target", "postgres", "migrate", "up"])

    second = runner.invoke(main, ["--target", "postgres", "migrate", "up"])

    assert second.exit_code == 0
    assert json.loads(second.output)["applied"] == 0
