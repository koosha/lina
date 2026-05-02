"""Unit tests for `lina-redshift run`, `explain`, and `list-templates`."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from lina_redshift.cli import main


def _bootstrap(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", pg_dsn)
    runner = CliRunner()
    runner.invoke(main, ["--target", "postgres", "migrate", "up"])
    runner.invoke(main, ["--target", "postgres", "seed", "--named-only"])


@pytest.mark.unit
def test_list_templates(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap(pg_dsn, monkeypatch)
    runner = CliRunner()

    result = runner.invoke(main, ["--target", "postgres", "list-templates"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    types = {t["query_type"] for t in payload}
    assert types == {
        "matter_lookup",
        "matter_spend_summary",
        "vendor_spend_summary",
        "timekeeper_rate_analysis",
        "invoice_search",
        "line_item_detail",
    }


@pytest.mark.unit
def test_run_matter_lookup(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap(pg_dsn, monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "--target",
            "postgres",
            "run",
            "matter_lookup",
            "--params",
            '{"matter_id": "matter_acme_v_beta"}',
            "--user-id",
            "user_jane",
            "--caller-roles",
            "legal_ops",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["row_count"] == 1
    assert payload["metrics"][0]["matter_name"] == "Acme v. Beta Litigation"


@pytest.mark.unit
def test_run_returns_error_packet_for_unauthorized(
    pg_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap(pg_dsn, monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "--target",
            "postgres",
            "run",
            "matter_spend_summary",
            "--params",
            "{}",
            "--user-id",
            "user_x",
            "--caller-roles",
            "random",
        ],
    )

    assert result.exit_code == 0  # CLI returns 0 even for error packets; payload conveys
    payload = json.loads(result.stdout)
    assert payload["error"]["type"] == "AuthorizationError"


@pytest.mark.unit
def test_explain_renders_sql_without_executing(
    pg_dsn: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap(pg_dsn, monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "--target",
            "postgres",
            "explain",
            "matter_lookup",
            "--params",
            '{"matter_id": "matter_acme_v_beta"}',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "vw_matter_current" in payload["sql"]
    assert "explain_plan" in payload
