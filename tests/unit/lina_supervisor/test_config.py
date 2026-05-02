"""Unit tests for SupervisorConfig + resolve_config."""

from __future__ import annotations

import pytest

from lina_supervisor.config import (
    MissingApiKeyError,
    SupervisorConfig,
    resolve_config,
)


@pytest.mark.unit
def test_default_model_is_gpt_4o() -> None:
    cfg = SupervisorConfig(openai_api_key="sk-test")
    assert cfg.model == "gpt-4o"


@pytest.mark.unit
def test_default_max_worker_calls_is_8() -> None:
    cfg = SupervisorConfig(openai_api_key="sk-test")
    assert cfg.max_worker_calls == 8


@pytest.mark.unit
def test_resolve_config_from_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("LINA_SUPERVISOR_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("LINA_SUPERVISOR_MAX_WORKER_CALLS", "12")
    cfg = resolve_config()
    assert cfg.openai_api_key == "sk-env"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.max_worker_calls == 12


@pytest.mark.unit
def test_resolve_config_requires_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(MissingApiKeyError):
        resolve_config()


@pytest.mark.unit
def test_resolve_config_reads_max_tokens_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("LINA_SUPERVISOR_ROUTE_MAX_TOKENS", "1024")
    monkeypatch.setenv("LINA_SUPERVISOR_SYNTHESIZE_MAX_TOKENS", "2048")
    monkeypatch.setenv("LINA_SUPERVISOR_REQUEST_TIMEOUT_SECONDS", "30")
    cfg = resolve_config()
    assert cfg.route_max_tokens == 1024
    assert cfg.synthesize_max_tokens == 2048
    assert cfg.request_timeout_seconds == 30
