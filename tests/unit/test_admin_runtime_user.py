"""Unit tests for the runtime-user bootstrap (Wave 4 / P0.3)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lina_redshift.admin.runtime_user import (
    RUNTIME_USERNAME,
    bootstrap_runtime_user,
    generate_password,
)


@pytest.mark.unit
def test_generate_password_uses_safe_alphabet_and_fixed_length() -> None:
    pw = generate_password()
    assert len(pw) == 32
    # Excludes shell-special characters that would otherwise need escaping
    # in runbook copy/paste flows or AWS CLI invocations.
    forbidden = set("\"'`$\\!*?(){}[]<>|;& \t\n\r")
    assert not (set(pw) & forbidden)


@pytest.mark.unit
def test_bootstrap_drops_creates_grants_and_commits() -> None:
    """All side effects happen on the cursor, in the documented order,
    inside a single transaction the bootstrap commits at the end.
    """
    cursor = MagicMock()
    cursor.fetchone.return_value = (7,)
    cursor_ctx = MagicMock()
    cursor_ctx.__enter__.return_value = cursor
    cursor_ctx.__exit__.return_value = False

    conn = MagicMock()
    conn.cursor.return_value = cursor_ctx

    result = bootstrap_runtime_user(admin_conn=conn, password="static-test-password")

    sqls = [call.args[0] for call in cursor.execute.call_args_list]
    assert any(s.startswith(f"DROP USER IF EXISTS {RUNTIME_USERNAME}") for s in sqls)
    assert any(s.startswith(f"CREATE USER {RUNTIME_USERNAME} PASSWORD") for s in sqls)
    assert any("GRANT USAGE ON SCHEMA public" in s for s in sqls)
    assert any("GRANT SELECT ON ALL TABLES IN SCHEMA public" in s for s in sqls)
    assert any(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES" in s for s in sqls
    )
    conn.commit.assert_called_once()
    assert result.username == RUNTIME_USERNAME
    assert result.password == "static-test-password"
    assert result.granted_tables == 7
    assert result.secret_arn is None
    assert result.secret_version_id is None


@pytest.mark.unit
def test_bootstrap_escapes_single_quotes_in_password() -> None:
    """`CREATE USER` doesn't accept placeholders for the password literal,
    so the bootstrap escapes single quotes by doubling them. This is
    defensive — `generate_password()` doesn't emit `'`, but a caller
    can override via `--password`.
    """
    cursor = MagicMock()
    cursor.fetchone.return_value = (0,)
    cursor_ctx = MagicMock()
    cursor_ctx.__enter__.return_value = cursor
    cursor_ctx.__exit__.return_value = False
    conn = MagicMock()
    conn.cursor.return_value = cursor_ctx

    bootstrap_runtime_user(admin_conn=conn, password="he's'tricky")

    create_sqls = [
        call.args[0]
        for call in cursor.execute.call_args_list
        if call.args[0].startswith("CREATE USER")
    ]
    assert len(create_sqls) == 1
    # The literal must contain doubled single quotes, not a raw `'`.
    assert "he''s''tricky" in create_sqls[0]
    assert "he's'tricky" not in create_sqls[0]


@pytest.mark.unit
def test_bootstrap_writes_secret_when_arn_supplied() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = (3,)
    cursor_ctx = MagicMock()
    cursor_ctx.__enter__.return_value = cursor
    cursor_ctx.__exit__.return_value = False
    conn = MagicMock()
    conn.cursor.return_value = cursor_ctx

    secrets = MagicMock()
    secrets.put_secret_value.return_value = {"VersionId": "ver-1"}

    result = bootstrap_runtime_user(
        admin_conn=conn,
        password="abc-123",
        secrets_client=secrets,
        put_secret_arn="arn:aws:secretsmanager:us-east-1:0:secret:foo",
    )

    secrets.put_secret_value.assert_called_once()
    call_kwargs = secrets.put_secret_value.call_args.kwargs
    assert call_kwargs["SecretId"] == "arn:aws:secretsmanager:us-east-1:0:secret:foo"
    # SecretString is a JSON envelope readable by the same Lambda code path
    # that already parses the admin secret.
    import json

    payload = json.loads(call_kwargs["SecretString"])
    assert payload == {"username": RUNTIME_USERNAME, "password": "abc-123"}
    assert result.secret_arn == "arn:aws:secretsmanager:us-east-1:0:secret:foo"
    assert result.secret_version_id == "ver-1"


@pytest.mark.unit
def test_bootstrap_rejects_secret_arn_without_client() -> None:
    cursor = MagicMock()
    cursor.fetchone.return_value = (0,)
    cursor_ctx = MagicMock()
    cursor_ctx.__enter__.return_value = cursor
    cursor_ctx.__exit__.return_value = False
    conn = MagicMock()
    conn.cursor.return_value = cursor_ctx

    with pytest.raises(ValueError, match="secrets_client"):
        bootstrap_runtime_user(
            admin_conn=conn,
            password="x",
            put_secret_arn="arn:foo",
        )
