"""Unit tests for the connection factory."""

from __future__ import annotations

import pytest

from lina_redshift.connection import (
    ConnectionConfig,
    MissingDsnError,
    resolve_config,
)


@pytest.mark.unit
def test_resolve_config_uses_postgres_dsn_when_target_postgres(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINA_POSTGRES_DSN", "postgresql://u:p@host:5432/db")
    monkeypatch.delenv("LINA_REDSHIFT_DSN", raising=False)

    cfg = resolve_config(target="postgres")

    assert cfg.dsn == "postgresql://u:p@host:5432/db"
    assert cfg.target == "postgres"


@pytest.mark.unit
def test_resolve_config_uses_redshift_dsn_when_target_redshift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
def test_connection_config_reads_statement_timeout_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LINA_STATEMENT_TIMEOUT_MS", "5000")
    monkeypatch.setenv("LINA_POSTGRES_DSN", "postgresql://localhost/x")

    cfg = resolve_config(target="postgres")

    assert cfg.statement_timeout_ms == 5000


# ---------------------------------------------------------------------------
# connect_with_kwargs / apply_session_settings (Wave 2)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_connect_with_kwargs_passes_each_field_to_psycopg2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Special-character passwords would silently break a `postgresql://` DSN.

    `connect_with_kwargs` builds the connection from explicit fields so
    psycopg2 never has to parse a URL. This is the regression test for
    the f-string DSN bug (P1.1).
    """
    from lina_redshift import connection as conn_module

    captured: dict[str, object] = {}

    class _FakeCursor:
        def __enter__(self) -> _FakeCursor:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def execute(self, *_a: object, **_k: object) -> None:
            return None

    class _FakeConn:
        def __init__(self) -> None:
            self.closed = False

        def cursor(self) -> _FakeCursor:
            return _FakeCursor()

        def close(self) -> None:
            self.closed = True

    def _fake_connect(**kwargs: object) -> _FakeConn:
        captured.update(kwargs)
        return _FakeConn()

    monkeypatch.setattr(conn_module.psycopg2, "connect", _fake_connect)

    weird_password = "p@ss/word:with#chars%and@signs"
    conn_module.connect_with_kwargs(
        host="rs.example.com",
        port=5439,
        dbname="dev",
        user="lina_app_readonly",
        password=weird_password,
        connect_timeout=7,
    )

    assert captured["host"] == "rs.example.com"
    assert captured["port"] == 5439
    assert captured["dbname"] == "dev"
    assert captured["user"] == "lina_app_readonly"
    assert captured["password"] == weird_password
    assert captured["connect_timeout"] == 7


@pytest.mark.unit
def test_connect_with_kwargs_applies_session_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """statement_timeout + read_only GUCs are applied right after connect."""
    from lina_redshift import connection as conn_module

    executed: list[tuple[str, object]] = []

    class _FakeCursor:
        def __enter__(self) -> _FakeCursor:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def execute(self, sql: str, params: object = None) -> None:
            executed.append((sql, params))

    class _FakeConn:
        def cursor(self) -> _FakeCursor:
            return _FakeCursor()

        def close(self) -> None:
            return None

    monkeypatch.setattr(conn_module.psycopg2, "connect", lambda **_: _FakeConn())

    conn_module.connect_with_kwargs(
        host="h",
        port=5439,
        dbname="d",
        user="u",
        password="p",
        statement_timeout_ms=12345,
        read_only=True,
    )

    sqls = [s for s, _ in executed]
    assert any("statement_timeout" in s for s in sqls)
    assert any("default_transaction_read_only = on" in s for s in sqls)
    assert any("transaction_read_only = on" in s for s in sqls)
    # Statement timeout value made it into the bound params.
    timeout_call = next((s, p) for s, p in executed if "statement_timeout" in s)
    assert timeout_call[1] == (12345,)


@pytest.mark.unit
def test_connect_with_kwargs_closes_conn_if_session_settings_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If `SET statement_timeout` fails, the partially-opened connection
    should not leak — close it before re-raising."""
    from lina_redshift import connection as conn_module

    closed = {"value": False}

    class _BadCursor:
        def __enter__(self) -> _BadCursor:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

        def execute(self, *_a: object, **_k: object) -> None:
            raise RuntimeError("bad GUC")

    class _FakeConn:
        def cursor(self) -> _BadCursor:
            return _BadCursor()

        def close(self) -> None:
            closed["value"] = True

    monkeypatch.setattr(conn_module.psycopg2, "connect", lambda **_: _FakeConn())

    with pytest.raises(RuntimeError, match="bad GUC"):
        conn_module.connect_with_kwargs(
            host="h",
            port=5439,
            dbname="d",
            user="u",
            password="p",
        )
    assert closed["value"] is True
