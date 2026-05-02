"""Unit tests for SupervisorConfig + resolve_config."""

from __future__ import annotations

import pytest

from lina_supervisor.config import (
    InvalidReasoningEffortError,
    MissingApiKeyError,
    SupervisorConfig,
    resolve_config,
)


@pytest.mark.unit
def test_default_model_is_gpt_5_2() -> None:
    cfg = SupervisorConfig(openai_api_key="sk-test")
    assert cfg.model == "gpt-5.2"


@pytest.mark.unit
def test_default_reasoning_effort_is_none() -> None:
    cfg = SupervisorConfig(openai_api_key="sk-test")
    assert cfg.reasoning_effort == "none"


@pytest.mark.unit
def test_default_max_worker_calls_is_8() -> None:
    cfg = SupervisorConfig(openai_api_key="sk-test")
    assert cfg.max_worker_calls == 8


@pytest.mark.unit
def test_resolve_config_from_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("LINA_SUPERVISOR_MODEL", "gpt-5.2-mini")
    monkeypatch.setenv("LINA_SUPERVISOR_MAX_WORKER_CALLS", "12")
    cfg = resolve_config()
    assert cfg.openai_api_key == "sk-env"
    assert cfg.model == "gpt-5.2-mini"
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


@pytest.mark.unit
@pytest.mark.parametrize("effort", ["none", "low", "medium", "high", "xhigh"])
def test_resolve_config_accepts_valid_reasoning_effort(
    monkeypatch: pytest.MonkeyPatch, effort: str
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("LINA_SUPERVISOR_REASONING_EFFORT", effort)
    cfg = resolve_config()
    assert cfg.reasoning_effort == effort


@pytest.mark.unit
def test_resolve_config_rejects_unknown_reasoning_effort(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    monkeypatch.setenv("LINA_SUPERVISOR_REASONING_EFFORT", "extreme")
    with pytest.raises(InvalidReasoningEffortError):
        resolve_config()
