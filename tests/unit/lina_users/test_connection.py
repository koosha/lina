"""Unit tests for lina_users connection factory."""

from __future__ import annotations

import pytest

from lina_users.connection import (
    MissingHostError,
    OpenSearchConfig,
    resolve_config,
)


@pytest.mark.unit
def test_resolve_config_basic_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_OPENSEARCH_HOST", "https://localhost:9200")
    monkeypatch.setenv("LINA_OPENSEARCH_AUTH", "basic")
    monkeypatch.setenv("LINA_OPENSEARCH_USER", "admin")
    monkeypatch.setenv("LINA_OPENSEARCH_PASSWORD", "admin")
    monkeypatch.delenv("LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS", raising=False)

    cfg = resolve_config()

    assert cfg.host == "https://localhost:9200"
    assert cfg.auth_mode == "basic"
    assert cfg.username == "admin"
    assert cfg.password == "admin"


@pytest.mark.unit
def test_resolve_config_aws_sigv4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_OPENSEARCH_HOST", "https://x.us-east-1.es.amazonaws.com")
    monkeypatch.setenv("LINA_OPENSEARCH_AUTH", "aws_sigv4")
    monkeypatch.setenv("LINA_AWS_REGION", "us-east-1")
    monkeypatch.delenv("LINA_OPENSEARCH_USER", raising=False)
    monkeypatch.delenv("LINA_OPENSEARCH_PASSWORD", raising=False)
    monkeypatch.delenv("LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS", raising=False)

    cfg = resolve_config()

    assert cfg.auth_mode == "aws_sigv4"
    assert cfg.aws_region == "us-east-1"


@pytest.mark.unit
def test_resolve_config_no_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_OPENSEARCH_HOST", "http://localhost:9200")
    monkeypatch.setenv("LINA_OPENSEARCH_AUTH", "none")
    monkeypatch.delenv("LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS", raising=False)

    cfg = resolve_config()

    assert cfg.auth_mode == "none"


@pytest.mark.unit
def test_resolve_config_missing_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINA_OPENSEARCH_HOST", raising=False)

    with pytest.raises(MissingHostError):
        resolve_config()


@pytest.mark.unit
def test_default_request_timeout_seconds() -> None:
    cfg = OpenSearchConfig(host="http://x", auth_mode="none")
    assert cfg.request_timeout_seconds == 30


@pytest.mark.unit
def test_request_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_OPENSEARCH_HOST", "http://x")
    monkeypatch.setenv("LINA_OPENSEARCH_AUTH", "none")
    monkeypatch.setenv("LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS", "10")
    cfg = resolve_config()
    assert cfg.request_timeout_seconds == 10
