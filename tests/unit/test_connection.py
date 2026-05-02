"""Unit tests for the connection factory."""

from __future__ import annotations

import pytest

from lina_redshift.connection import (
    ConnectionConfig,
    MissingDsnError,
    resolve_config,
)


@pytest.mark.unit
def test_resolve_config_uses_postgres_dsn_when_target_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("LINA_REDSHIFT_DSN", raising=False)

    cfg = resolve_config(target="postgres")

    assert cfg.dsn == "postgresql://u:p@host:5432/db"
    assert cfg.target == "postgres"


@pytest.mark.unit
def test_resolve_config_uses_redshift_dsn_when_target_redshift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_REDSHIFT_DSN", "postgresql://u:p@cluster:5439/dev")
    monkeypatch.delenv("LINA_POSTGRES_DSN", raising=False)

    cfg = resolve_config(target="redshift")

    assert cfg.dsn == "postgresql://u:p@cluster:5439/dev"
    assert cfg.target == "redshift"


@pytest.mark.unit
def test_resolve_config_raises_when_dsn_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINA_REDSHIFT_DSN", raising=False)
    monkeypatch.delenv("LINA_POSTGRES_DSN", raising=False)

    with pytest.raises(MissingDsnError) as excinfo:
        resolve_config(target="redshift")

    assert "LINA_REDSHIFT_DSN" in str(excinfo.value)


@pytest.mark.unit
def test_connection_config_default_statement_timeout_ms() -> None:
    cfg = ConnectionConfig(dsn="postgresql://localhost/x", target="postgres")

    assert cfg.statement_timeout_ms == 30_000


@pytest.mark.unit
def test_connection_config_reads_statement_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_STATEMENT_TIMEOUT_MS", "5000")
    monkeypatch.setenv("LINA_POSTGRES_DSN", "postgresql://localhost/x")

    cfg = resolve_config(target="postgres")

    assert cfg.statement_timeout_ms == 5000
