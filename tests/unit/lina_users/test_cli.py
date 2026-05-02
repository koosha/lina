"""Unit tests for the `lina-users` CLI."""

from __future__ import annotations

import json
from typing import Any

import pytest
from click.testing import CliRunner

from lina_users.cli import main


@pytest.mark.unit
def test_list_templates_emits_json_for_all_four() -> None:
    """list-templates does not require an OpenSearch client."""
    runner = CliRunner()
    result = runner.invoke(main, ["list-templates"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    query_types = {entry["query_type"] for entry in payload}
    assert query_types == {"user_lookup", "user_search", "manager_chain", "people_filter"}
    for entry in payload:
        assert entry["index"] == "corp_user_profiles_v1"
        assert "params_schema" in entry


@pytest.mark.unit
def test_seed_rejects_named_only_and_bulk_only_together() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["seed", "--named-only", "--bulk-only"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.stderr or "mutually exclusive" in result.output


@pytest.mark.unit
def test_explain_emits_query_body_for_user_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """explain renders the OpenSearch DSL body even when the search call is stubbed."""

    class _StubClient:
        def search(self, **kwargs: Any) -> dict[str, Any]:
            return {"hits": {"hits": []}}

    monkeypatch.setenv("LINA_OPENSEARCH_HOST", "http://stubbed")
    monkeypatch.setenv("LINA_OPENSEARCH_AUTH", "none")

    import lina_users.cli as cli

    monkeypatch.setattr(cli, "open_client", lambda _cfg: _StubClient())

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "explain",
            "user_lookup",
            "--params",
            json.dumps({"user_id": "user_jane_smith"}),
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["query_type"] == "user_lookup"
    assert payload["index"] == "corp_user_profiles_v1"
    assert "query" in payload["sql"]


@pytest.mark.unit
def test_run_returns_error_packet_for_authorization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run returns a JSON ErrorPacket when the caller is not authorized."""

    class _StubClient:
        def search(self, **kwargs: Any) -> dict[str, Any]:
            return {"hits": {"hits": []}}

    monkeypatch.setenv("LINA_OPENSEARCH_HOST", "http://stubbed")
    monkeypatch.setenv("LINA_OPENSEARCH_AUTH", "none")

    import lina_users.cli as cli

    monkeypatch.setattr(cli, "open_client", lambda _cfg: _StubClient())

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "run",
            "manager_chain",
            "--params",
            json.dumps({"start_user_id": "user_jane_smith"}),
            "--user-id",
            "caller_test",
            "--caller-roles",
            "billing_clerk",  # not legal_ops or hr_ops
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["error"]["type"] == "AuthorizationError"
