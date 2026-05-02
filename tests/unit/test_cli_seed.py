"""Unit tests for `lina-redshift seed`."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from lina_redshift.cli import main


@pytest.mark.unit
def test_seed_full_load(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", pg_dsn)
    runner = CliRunner()

    runner.invoke(main, ["--target", "postgres", "migrate", "up"])
    result = runner.invoke(main, ["--target", "postgres", "seed"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["loaded"] is True


@pytest.mark.unit
def test_seed_named_only(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", pg_dsn)
    runner = CliRunner()
    runner.invoke(main, ["--target", "postgres", "migrate", "up"])

    result = runner.invoke(main, ["--target", "postgres", "seed", "--named-only"])

    assert result.exit_code == 0


@pytest.mark.unit
def test_seed_reset_runs(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", pg_dsn)
    runner = CliRunner()
    runner.invoke(main, ["--target", "postgres", "migrate", "up"])
    runner.invoke(main, ["--target", "postgres", "seed"])

    result = runner.invoke(main, ["--target", "postgres", "seed", "--reset"])

    assert result.exit_code == 0
