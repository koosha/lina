# LINA Redshift Worker (Subsystem C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python 3.12 package + CLI that exposes a Redshift query worker over a typed catalog of 6 read-only templates, backed by the `legal_matter_spend` schema (12 tables + 4 governed views/MVs) and a deterministic seed dataset.

**Architecture:** Pure parameterized templates (no free-form SQL); every template is a typed pydantic class with a static SQL body, AST-validated at import. Two-tier testing: Postgres-in-Docker for unit/TDD, Redshift Serverless for integration parity. Migrations are plain numbered `.sql` files in Redshift dialect with a regex-based portability shim for Postgres.

**Tech Stack:** Python 3.12, pydantic v2, sqlglot, psycopg2-binary, structlog, click, Faker, python-ulid, pytest, pytest-postgresql, mypy, ruff.

**Spec reference:** `docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md`. Cross-reference `lina.md` §3 + §13 for source spec.

**Note on dependencies:** The spec lists `redshift-connector` as a runtime dep. For v1 (DSN-only, Q9 option a), `psycopg2-binary` connects to both Postgres and Redshift over the Postgres wire protocol; `redshift-connector` becomes necessary only when IAM auth lands (deferred). Plan installs `psycopg2-binary` only.

---

## File Structure

```text
lina/
├── pyproject.toml
├── ruff.toml
├── mypy.ini
├── pytest.ini
├── .gitignore
├── README.md
├── lina.md                              # existing
├── docs/superpowers/specs/...            # existing
├── docs/superpowers/plans/...            # this file
├── src/lina_redshift/
│   ├── __init__.py
│   ├── connection.py                    # DSN factory
│   ├── dialect.py                       # Postgres↔Redshift shim
│   ├── caller.py                        # CallerContext model
│   ├── errors.py                        # typed exceptions
│   ├── packet.py                        # ResultPacket model
│   ├── logging_config.py                # structlog setup
│   ├── worker.py                        # RedshiftWorker.run()
│   ├── migrations/
│   │   ├── runner.py
│   │   └── sql/001_dim_legal_entity.sql … 018_mv_timekeeper_rate_analysis.sql
│   ├── templates/
│   │   ├── __init__.py                  # TEMPLATE_REGISTRY
│   │   ├── base.py                      # QueryTemplate ABC + AST validator
│   │   ├── matter_lookup.py
│   │   ├── matter_spend_summary.py
│   │   ├── vendor_spend_summary.py
│   │   ├── timekeeper_rate_analysis.py
│   │   ├── invoice_search.py
│   │   └── line_item_detail.py
│   ├── seed/
│   │   ├── __init__.py                  # load_all
│   │   ├── billing_codes.py
│   │   ├── named_entities.py
│   │   └── generator.py                 # Faker bulk
│   └── cli.py                           # `lina-redshift`
└── tests/
    ├── conftest.py
    ├── unit/test_*.py                    # @pytest.mark.unit
    └── integration/test_*.py             # @pytest.mark.integration
```

---

## Task 1: Project Bootstrap

**Files:**
- Create: `pyproject.toml`
- Create: `ruff.toml`
- Create: `mypy.ini`
- Create: `pytest.ini`
- Create: `.gitignore`
- Create: `src/lina_redshift/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd "/Users/mb16/My Drive (koosha.g@gmail.com)/code/lina"
git init
git add lina.md docs/
git commit -m "chore: import source spec and design doc"
```

- [ ] **Step 2: Create `.gitignore`**

```text
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.env
.env.local
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
dist/
build/
*.sqlite
.DS_Store
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "lina-redshift"
version = "0.1.0"
description = "LINA — Redshift matter & spend worker (Subsystem C)"
requires-python = ">=3.12"
dependencies = [
    "psycopg2-binary>=2.9.9",
    "pydantic>=2.6",
    "sqlglot>=23.0",
    "python-ulid>=2.2",
    "structlog>=24.1",
    "click>=8.1",
    "Faker>=24.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.1",
    "pytest-postgresql>=5.1",
    "mypy>=1.9",
    "ruff>=0.3",
    "coverage[toml]>=7.4",
]

[project.scripts]
lina-redshift = "lina_redshift.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
lina_redshift = ["migrations/sql/*.sql"]

[tool.coverage.run]
source = ["src/lina_redshift"]
branch = true
```

- [ ] **Step 4: Create `ruff.toml`**

```toml
target-version = "py312"
line-length = 100

[lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "SIM", "C4", "PTH", "RET", "ARG"]
ignore = ["E501"]  # line length handled by formatter

[lint.per-file-ignores]
"tests/**" = ["ARG"]
```

- [ ] **Step 5: Create `mypy.ini`**

```ini
[mypy]
python_version = 3.12
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
files = src/lina_redshift

[mypy-faker.*]
ignore_missing_imports = true

[mypy-pytest_postgresql.*]
ignore_missing_imports = true
```

- [ ] **Step 6: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
markers =
    unit: fast tests against ephemeral Postgres (default)
    integration: slow tests against Redshift Serverless (requires LINA_REDSHIFT_DSN)
addopts = -m unit --strict-markers -ra
```

- [ ] **Step 7: Create empty package files**

`src/lina_redshift/__init__.py`:
```python
"""LINA Redshift matter & spend worker (Subsystem C)."""

__version__ = "0.1.0"
```

`tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`: each empty file.

- [ ] **Step 8: Create initial `tests/conftest.py`**

```python
"""Shared pytest fixtures for unit and integration suites."""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests when LINA_REDSHIFT_DSN is unset."""
    if os.environ.get("LINA_REDSHIFT_DSN"):
        return
    skip_integration = pytest.mark.skip(reason="LINA_REDSHIFT_DSN not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
```

- [ ] **Step 9: Install dependencies**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
```

Expected: package and dev dependencies installed without errors.

- [ ] **Step 10: Verify the toolchain**

```bash
ruff check src tests
mypy
pytest --collect-only
```

Expected: all three commands exit 0. `pytest --collect-only` reports "0 tests collected".

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml ruff.toml mypy.ini pytest.ini .gitignore src tests
git commit -m "chore: bootstrap python package and toolchain"
```

---

## Task 2: Connection Factory

**Files:**
- Create: `src/lina_redshift/connection.py`
- Create: `tests/unit/test_connection.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the failing test for DSN parsing**

`tests/unit/test_connection.py`:
```python
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
```

- [ ] **Step 2: Run the test to confirm failure**

Run: `pytest tests/unit/test_connection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lina_redshift.connection'`.

- [ ] **Step 3: Implement `connection.py`**

`src/lina_redshift/connection.py`:
```python
"""Connection factory for Postgres (dev/unit) and Redshift (integration/prod)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal

import psycopg2
from psycopg2.extensions import connection as PgConnection

Target = Literal["postgres", "redshift"]


class MissingDsnError(RuntimeError):
    """Raised when the required DSN environment variable is unset."""


@dataclass(frozen=True)
class ConnectionConfig:
    dsn: str
    target: Target
    statement_timeout_ms: int = 30_000

    def env_var_name(self) -> str:
        return "LINA_REDSHIFT_DSN" if self.target == "redshift" else "LINA_POSTGRES_DSN"


def resolve_config(target: Target = "redshift") -> ConnectionConfig:
    env_name = "LINA_REDSHIFT_DSN" if target == "redshift" else "LINA_POSTGRES_DSN"
    dsn = os.environ.get(env_name)
    if not dsn:
        raise MissingDsnError(
            f"{env_name} is not set. Export it before invoking lina-redshift."
        )
    timeout_str = os.environ.get("LINA_STATEMENT_TIMEOUT_MS", "30000")
    return ConnectionConfig(dsn=dsn, target=target, statement_timeout_ms=int(timeout_str))


@contextmanager
def open_connection(config: ConnectionConfig, *, read_only: bool = True) -> Iterator[PgConnection]:
    """Open a connection with read-only and statement-timeout GUCs applied."""
    conn = psycopg2.connect(config.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (config.statement_timeout_ms,))
            if read_only:
                cur.execute("SET default_transaction_read_only = on")
                cur.execute("SET transaction_read_only = on")
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 4: Run the unit tests to confirm they pass**

Run: `pytest tests/unit/test_connection.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run mypy and ruff**

Run: `mypy && ruff check src tests`
Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/connection.py tests/unit/test_connection.py
git commit -m "feat(connection): add DSN-based connection factory with read-only and timeout GUCs"
```

---

## Task 3: Dialect Shim

**Files:**
- Create: `src/lina_redshift/dialect.py`
- Create: `tests/unit/test_dialect_shim.py`

- [ ] **Step 1: Write failing tests for every translation rule**

`tests/unit/test_dialect_shim.py`:
```python
"""Unit tests for the Redshift→Postgres dialect shim."""

from __future__ import annotations

import pytest

from lina_redshift.dialect import (
    UnsupportedDialectError,
    translate_for_postgres,
)


@pytest.mark.unit
def test_strips_diststyle_auto() -> None:
    sql = "CREATE TABLE t (id varchar) DISTSTYLE AUTO;"
    assert "DISTSTYLE" not in translate_for_postgres(sql)


@pytest.mark.unit
def test_strips_diststyle_key() -> None:
    sql = "CREATE TABLE t (id varchar) DISTKEY(id) DISTSTYLE KEY(id);"
    out = translate_for_postgres(sql)
    assert "DISTSTYLE" not in out
    assert "DISTKEY" not in out


@pytest.mark.unit
def test_strips_diststyle_even() -> None:
    assert "DISTSTYLE" not in translate_for_postgres("CREATE TABLE t (id int) DISTSTYLE EVEN;")


@pytest.mark.unit
def test_strips_diststyle_all() -> None:
    assert "DISTSTYLE" not in translate_for_postgres("CREATE TABLE t (id int) DISTSTYLE ALL;")


@pytest.mark.unit
def test_strips_sortkey_auto() -> None:
    assert "SORTKEY" not in translate_for_postgres("CREATE TABLE t (id int) SORTKEY AUTO;")


@pytest.mark.unit
def test_strips_sortkey_columns() -> None:
    sql = "CREATE TABLE t (id int, dt date) SORTKEY (dt, id);"
    assert "SORTKEY" not in translate_for_postgres(sql)


@pytest.mark.unit
def test_strips_compound_sortkey() -> None:
    sql = "CREATE TABLE t (id int, dt date) COMPOUND SORTKEY(dt);"
    assert "SORTKEY" not in translate_for_postgres(sql)


@pytest.mark.unit
def test_strips_interleaved_sortkey() -> None:
    sql = "CREATE TABLE t (id int, dt date) INTERLEAVED SORTKEY(dt, id);"
    assert "SORTKEY" not in translate_for_postgres(sql)


@pytest.mark.unit
@pytest.mark.parametrize(
    "encoding",
    ["AZ64", "LZO", "ZSTD", "RAW", "BYTEDICT", "DELTA", "MOSTLY8", "MOSTLY16",
     "MOSTLY32", "RUNLENGTH", "TEXT255", "TEXT32K"],
)
def test_strips_column_encode(encoding: str) -> None:
    sql = f"CREATE TABLE t (id varchar ENCODE {encoding});"
    out = translate_for_postgres(sql)
    assert "ENCODE" not in out


@pytest.mark.unit
def test_strips_backup_no() -> None:
    sql = "CREATE TABLE t (id int) BACKUP NO;"
    assert "BACKUP" not in translate_for_postgres(sql)


@pytest.mark.unit
def test_strips_backup_yes() -> None:
    sql = "CREATE TABLE t (id int) BACKUP YES;"
    assert "BACKUP" not in translate_for_postgres(sql)


@pytest.mark.unit
def test_replaces_identity_with_generated() -> None:
    sql = "CREATE TABLE t (id int IDENTITY(1, 1));"
    out = translate_for_postgres(sql)
    assert "IDENTITY" not in out
    assert "GENERATED BY DEFAULT AS IDENTITY" in out


@pytest.mark.unit
def test_strips_auto_refresh_yes() -> None:
    sql = "CREATE MATERIALIZED VIEW mv AS SELECT 1 AUTO REFRESH YES;"
    out = translate_for_postgres(sql)
    assert "AUTO REFRESH" not in out


@pytest.mark.unit
def test_replaces_varchar_max() -> None:
    sql = "CREATE TABLE t (note varchar(max));"
    out = translate_for_postgres(sql)
    assert "varchar(max)" not in out
    assert "varchar" in out  # plain varchar with no length is unlimited in Postgres


@pytest.mark.unit
def test_idempotent_when_no_redshift_clauses() -> None:
    sql = "CREATE TABLE t (id varchar PRIMARY KEY);"
    assert translate_for_postgres(sql) == sql


@pytest.mark.unit
def test_unknown_redshift_only_token_raises() -> None:
    sql = "CREATE TABLE t (data SUPER);"
    with pytest.raises(UnsupportedDialectError):
        translate_for_postgres(sql)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/unit/test_dialect_shim.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `dialect.py`**

`src/lina_redshift/dialect.py`:
```python
"""Translate Redshift-flavored DDL to Postgres-compatible DDL.

Production target is Redshift. The shim runs only when the migration runner
targets Postgres (unit tests, local dev). Each translation has a unit test.
"""

from __future__ import annotations

import re


class UnsupportedDialectError(RuntimeError):
    """Raised when input SQL contains Redshift-only constructs we do not handle."""


_ENCODINGS = (
    "AZ64", "LZO", "ZSTD", "RAW", "BYTEDICT", "DELTA",
    "MOSTLY8", "MOSTLY16", "MOSTLY32", "RUNLENGTH", "TEXT255", "TEXT32K",
)
_ENCODE_RE = re.compile(
    r"\s+ENCODE\s+(?:" + "|".join(_ENCODINGS) + r")",
    flags=re.IGNORECASE,
)

_DISTSTYLE_RE = re.compile(
    r"\s+DISTSTYLE\s+(?:AUTO|EVEN|ALL|KEY\s*\([^)]*\))",
    flags=re.IGNORECASE,
)
_DISTKEY_RE = re.compile(r"\s+DISTKEY\s*\([^)]*\)", flags=re.IGNORECASE)

_SORTKEY_RE = re.compile(
    r"\s+(?:COMPOUND\s+|INTERLEAVED\s+)?SORTKEY\s+"
    r"(?:AUTO|\([^)]*\))",
    flags=re.IGNORECASE,
)

_BACKUP_RE = re.compile(r"\s+BACKUP\s+(?:YES|NO)", flags=re.IGNORECASE)

_IDENTITY_RE = re.compile(
    r"\bIDENTITY\s*\(\s*\d+\s*,\s*\d+\s*\)",
    flags=re.IGNORECASE,
)

_AUTO_REFRESH_RE = re.compile(r"\s+AUTO\s+REFRESH\s+(?:YES|NO)", flags=re.IGNORECASE)

_VARCHAR_MAX_RE = re.compile(r"varchar\s*\(\s*max\s*\)", flags=re.IGNORECASE)

# Redshift-only tokens we have not implemented translations for.
_UNSUPPORTED_TOKENS = (
    re.compile(r"\bSUPER\b", flags=re.IGNORECASE),
    re.compile(r"\bHLLSKETCH\b", flags=re.IGNORECASE),
    re.compile(r"\bGEOMETRY\b", flags=re.IGNORECASE),
)


def translate_for_postgres(sql: str) -> str:
    """Apply all Redshift→Postgres translations. Raise on unsupported constructs."""
    for token_re in _UNSUPPORTED_TOKENS:
        if token_re.search(sql):
            raise UnsupportedDialectError(
                f"SQL contains Redshift-only construct not handled by the shim: {sql!r}"
            )
    out = sql
    out = _ENCODE_RE.sub("", out)
    out = _DISTSTYLE_RE.sub("", out)
    out = _DISTKEY_RE.sub("", out)
    out = _SORTKEY_RE.sub("", out)
    out = _BACKUP_RE.sub("", out)
    out = _AUTO_REFRESH_RE.sub("", out)
    out = _IDENTITY_RE.sub("GENERATED BY DEFAULT AS IDENTITY", out)
    out = _VARCHAR_MAX_RE.sub("varchar", out)
    return out
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `pytest tests/unit/test_dialect_shim.py -v`
Expected: 27 passed (12 encoding parametrize cases + 15 others).

- [ ] **Step 5: Run mypy and ruff**

Run: `mypy && ruff check src tests`
Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/dialect.py tests/unit/test_dialect_shim.py
git commit -m "feat(dialect): add Redshift-to-Postgres DDL portability shim"
```

---

## Task 4: Migration Runner

**Files:**
- Create: `src/lina_redshift/migrations/__init__.py`
- Create: `src/lina_redshift/migrations/runner.py`
- Create: `src/lina_redshift/migrations/sql/.gitkeep`
- Create: `tests/unit/test_migration_runner.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add Postgres fixture to `tests/conftest.py`**

Replace `tests/conftest.py` with:
```python
"""Shared pytest fixtures for unit and integration suites."""

from __future__ import annotations

import os
from typing import Iterator

import psycopg2
import pytest
from psycopg2.extensions import connection as PgConnection
from pytest_postgresql import factories

postgresql_proc = factories.postgresql_proc(port=None, unixsocketdir="/tmp")
postgresql_db = factories.postgresql("postgresql_proc", dbname="lina_test")


@pytest.fixture
def pg_dsn(postgresql_db: PgConnection) -> str:
    """DSN for the per-test Postgres database."""
    info = postgresql_db.info
    return (
        f"postgresql://{info.user}@{info.host}:{info.port}/{info.dbname}"
    )


@pytest.fixture
def pg_conn(pg_dsn: str) -> Iterator[PgConnection]:
    conn = psycopg2.connect(pg_dsn)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests when LINA_REDSHIFT_DSN is unset."""
    if os.environ.get("LINA_REDSHIFT_DSN"):
        return
    skip_integration = pytest.mark.skip(reason="LINA_REDSHIFT_DSN not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
```

- [ ] **Step 2: Write failing tests for the runner**

`tests/unit/test_migration_runner.py`:
```python
"""Unit tests for the migration runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import (
    MigrationRunner,
    list_pending,
)


@pytest.fixture
def sql_dir(tmp_path: Path) -> Path:
    d = tmp_path / "sql"
    d.mkdir()
    (d / "001_first.sql").write_text("CREATE TABLE thing_one (id varchar PRIMARY KEY);")
    (d / "002_second.sql").write_text(
        "CREATE TABLE thing_two (id varchar PRIMARY KEY, ref varchar);"
    )
    return d


@pytest.mark.unit
def test_apply_pending_creates_migrations_table(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")

    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT version FROM schema_migrations ORDER BY version",
        )
        rows = [r[0] for r in cur.fetchall()]
    assert rows == ["001_first", "002_second"]


@pytest.mark.unit
def test_apply_pending_creates_target_tables(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")

    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'thing_%' ORDER BY table_name"
        )
        rows = [r[0] for r in cur.fetchall()]
    assert rows == ["thing_one", "thing_two"]


@pytest.mark.unit
def test_apply_pending_is_idempotent(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")
    runner.apply_pending()

    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM schema_migrations")
        assert cur.fetchone()[0] == 2


@pytest.mark.unit
def test_apply_pending_applies_only_new_files(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")
    runner.apply_pending()

    (sql_dir / "003_third.sql").write_text(
        "CREATE TABLE thing_three (id varchar PRIMARY KEY);"
    )
    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations ORDER BY version")
        rows = [r[0] for r in cur.fetchall()]
    assert rows == ["001_first", "002_second", "003_third"]


@pytest.mark.unit
def test_list_pending_returns_unapplied(pg_conn: PgConnection, sql_dir: Path) -> None:
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")
    runner.apply_pending()
    (sql_dir / "003_third.sql").write_text("CREATE TABLE thing_three (id varchar);")

    pending = list_pending(connection=pg_conn, sql_dir=sql_dir)

    assert pending == ["003_third"]


@pytest.mark.unit
def test_apply_pending_translates_redshift_dialect_for_postgres(
    pg_conn: PgConnection, tmp_path: Path,
) -> None:
    sql_dir = tmp_path / "sql"
    sql_dir.mkdir()
    (sql_dir / "001_redshift.sql").write_text(
        "CREATE TABLE rs_thing (id varchar PRIMARY KEY, note varchar(max)) "
        "DISTSTYLE AUTO SORTKEY AUTO;"
    )
    runner = MigrationRunner(connection=pg_conn, sql_dir=sql_dir, target="postgres")

    runner.apply_pending()

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = 'rs_thing' ORDER BY column_name"
        )
        rows = cur.fetchall()
    assert rows == [("id", "character varying"), ("note", "character varying")]
```

- [ ] **Step 3: Run tests to confirm failure**

Run: `pytest tests/unit/test_migration_runner.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement `migrations/__init__.py`**

`src/lina_redshift/migrations/__init__.py`:
```python
"""DDL migrations for the legal_matter_spend schema."""
```

- [ ] **Step 5: Implement `migrations/runner.py`**

`src/lina_redshift/migrations/runner.py`:
```python
"""Apply numbered .sql migration files in order, recording version state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from psycopg2.extensions import connection as PgConnection

from lina_redshift.dialect import translate_for_postgres

Target = Literal["postgres", "redshift"]

_MIGRATIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version varchar PRIMARY KEY,
    applied_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


@dataclass
class MigrationRunner:
    connection: PgConnection
    sql_dir: Path
    target: Target

    def apply_pending(self) -> list[str]:
        applied: list[str] = []
        self._ensure_migrations_table()
        already = self._already_applied()
        for path in sorted(self.sql_dir.glob("*.sql")):
            version = path.stem
            if version in already:
                continue
            sql = path.read_text()
            if self.target == "postgres":
                sql = translate_for_postgres(sql)
            self._execute_migration(version=version, sql=sql)
            applied.append(version)
        return applied

    def _ensure_migrations_table(self) -> None:
        with self.connection.cursor() as cur:
            cur.execute(_MIGRATIONS_TABLE_DDL)
        self.connection.commit()

    def _already_applied(self) -> set[str]:
        with self.connection.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations")
            return {row[0] for row in cur.fetchall()}

    def _execute_migration(self, *, version: str, sql: str) -> None:
        with self.connection.cursor() as cur:
            if self.target == "postgres":
                cur.execute(sql)
            else:
                # Redshift: split on top-level ';' and run statements individually,
                # since some Redshift DDL does not support transactions.
                for statement in _split_statements(sql):
                    if statement.strip():
                        cur.execute(statement)
            cur.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)",
                (version,),
            )
        self.connection.commit()


def _split_statements(sql: str) -> list[str]:
    """Split SQL on top-level semicolons. Naive but sufficient for our DDL files."""
    out: list[str] = []
    buf: list[str] = []
    paren_depth = 0
    in_single = False
    for ch in sql:
        if ch == "'" and not in_single:
            in_single = True
        elif ch == "'" and in_single:
            in_single = False
        elif not in_single:
            if ch == "(":
                paren_depth += 1
            elif ch == ")":
                paren_depth -= 1
            elif ch == ";" and paren_depth == 0:
                out.append("".join(buf))
                buf = []
                continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def list_pending(*, connection: PgConnection, sql_dir: Path) -> list[str]:
    with connection.cursor() as cur:
        cur.execute("SELECT version FROM schema_migrations")
        already = {row[0] for row in cur.fetchall()}
    return [p.stem for p in sorted(sql_dir.glob("*.sql")) if p.stem not in already]
```

- [ ] **Step 6: Create `migrations/sql/.gitkeep`**

`src/lina_redshift/migrations/sql/.gitkeep`: empty file.

- [ ] **Step 7: Run tests to confirm pass**

Run: `pytest tests/unit/test_migration_runner.py -v`
Expected: 6 passed.

- [ ] **Step 8: Run mypy and ruff**

Run: `mypy && ruff check src tests`
Expected: both exit 0.

- [ ] **Step 9: Commit**

```bash
git add src/lina_redshift/migrations tests/unit/test_migration_runner.py tests/conftest.py
git commit -m "feat(migrations): add migration runner with dialect-aware translation"
```

---

## Task 5: Reference Dimension Migrations (001–003)

**Files:**
- Create: `src/lina_redshift/migrations/sql/001_dim_legal_entity.sql`
- Create: `src/lina_redshift/migrations/sql/002_dim_cost_center.sql`
- Create: `src/lina_redshift/migrations/sql/003_dim_billing_code.sql`
- Create: `tests/unit/test_migrations_reference_dims.py`

- [ ] **Step 1: Write `001_dim_legal_entity.sql`**

```sql
CREATE TABLE IF NOT EXISTS dim_legal_entity (
    legal_entity_id varchar PRIMARY KEY,
    legal_entity_name varchar NOT NULL,
    country_code char(2),
    entity_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE ALL
SORTKEY (legal_entity_id);
```

- [ ] **Step 2: Write `002_dim_cost_center.sql`**

```sql
CREATE TABLE IF NOT EXISTS dim_cost_center (
    cost_center_id varchar PRIMARY KEY,
    cost_center_name varchar NOT NULL,
    business_unit varchar,
    department varchar,
    active_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE ALL
SORTKEY (cost_center_id);
```

- [ ] **Step 3: Write `003_dim_billing_code.sql`**

```sql
CREATE TABLE IF NOT EXISTS dim_billing_code (
    billing_code_id varchar PRIMARY KEY,
    code varchar NOT NULL,
    code_type varchar NOT NULL,
    code_set varchar NOT NULL,
    description varchar NOT NULL,
    active_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE ALL
SORTKEY (code_set, code);
```

- [ ] **Step 4: Write the failing migration test**

`tests/unit/test_migrations_reference_dims.py`:
```python
"""Verify reference dimension migrations create expected tables."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


def _columns(conn: PgConnection, table: str) -> list[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position",
            (table,),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    runner = MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres")
    runner.apply_pending()
    return pg_conn


@pytest.mark.unit
def test_dim_legal_entity_exists(applied: PgConnection) -> None:
    cols = dict(_columns(applied, "dim_legal_entity"))
    assert cols["legal_entity_id"] == "character varying"
    assert cols["legal_entity_name"] == "character varying"
    assert cols["entity_status"] == "character varying"
    assert cols["created_at"] == "timestamp without time zone"


@pytest.mark.unit
def test_dim_cost_center_exists(applied: PgConnection) -> None:
    cols = dict(_columns(applied, "dim_cost_center"))
    assert "cost_center_id" in cols
    assert "cost_center_name" in cols
    assert "active_status" in cols


@pytest.mark.unit
def test_dim_billing_code_exists(applied: PgConnection) -> None:
    cols = dict(_columns(applied, "dim_billing_code"))
    assert "billing_code_id" in cols
    assert cols["code_type"] == "character varying"
    assert cols["code_set"] == "character varying"
```

- [ ] **Step 5: Run test to confirm pass**

Run: `pytest tests/unit/test_migrations_reference_dims.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/migrations/sql tests/unit/test_migrations_reference_dims.py
git commit -m "feat(migrations): add reference dimensions (legal_entity, cost_center, billing_code)"
```

---

## Task 6: Vendor and Matter Dimensions (004–005)

**Files:**
- Create: `src/lina_redshift/migrations/sql/004_dim_vendor.sql`
- Create: `src/lina_redshift/migrations/sql/005_dim_matter.sql`
- Create: `tests/unit/test_migrations_vendor_matter.py`

- [ ] **Step 1: Write `004_dim_vendor.sql`**

```sql
CREATE TABLE IF NOT EXISTS dim_vendor (
    vendor_id varchar PRIMARY KEY,
    vendor_name varchar NOT NULL,
    vendor_type varchar NOT NULL,
    vendor_status varchar NOT NULL,
    primary_contact_name varchar,
    primary_contact_email varchar,
    billing_contact_email varchar,
    country_code char(2),
    default_currency_code char(3),
    preferred_panel_flag boolean,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL,
    source_system varchar NOT NULL
)
DISTSTYLE ALL
SORTKEY (vendor_id);
```

- [ ] **Step 2: Write `005_dim_matter.sql`**

```sql
CREATE TABLE IF NOT EXISTS dim_matter (
    matter_id varchar PRIMARY KEY,
    client_matter_id varchar NOT NULL,
    matter_number varchar,
    matter_name varchar NOT NULL,
    matter_description varchar(max),
    matter_status varchar NOT NULL,
    matter_type varchar NOT NULL,
    practice_area varchar,
    area_of_law_code varchar,
    service_code varchar,
    industry_code varchar,
    jurisdiction varchar,
    risk_level varchar,
    complexity_level varchar,
    open_date date NOT NULL,
    close_date date,
    legal_entity_id varchar,
    business_unit varchar,
    cost_center_id varchar,
    matter_owner_user_id varchar,
    lead_inhouse_counsel_user_id varchar,
    invoice_approver_user_id varchar,
    budget_amount decimal(18, 2),
    budget_currency_code char(3),
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL,
    source_system varchar NOT NULL
)
DISTSTYLE KEY (matter_id)
SORTKEY (matter_status, open_date);
```

- [ ] **Step 3: Write failing tests**

`tests/unit/test_migrations_vendor_matter.py`:
```python
"""Verify vendor and matter dimension migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    runner = MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres")
    runner.apply_pending()
    return pg_conn


def _column_names(conn: PgConnection, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


@pytest.mark.unit
def test_dim_vendor_columns(applied: PgConnection) -> None:
    cols = _column_names(applied, "dim_vendor")
    expected = {
        "vendor_id", "vendor_name", "vendor_type", "vendor_status",
        "primary_contact_name", "primary_contact_email", "billing_contact_email",
        "country_code", "default_currency_code", "preferred_panel_flag",
        "created_at", "updated_at", "source_system",
    }
    assert expected <= cols


@pytest.mark.unit
def test_dim_matter_columns(applied: PgConnection) -> None:
    cols = _column_names(applied, "dim_matter")
    expected = {
        "matter_id", "client_matter_id", "matter_name", "matter_description",
        "matter_status", "matter_type", "practice_area", "open_date",
        "close_date", "matter_owner_user_id", "budget_amount", "budget_currency_code",
    }
    assert expected <= cols


@pytest.mark.unit
def test_dim_matter_accepts_unbounded_description(applied: PgConnection) -> None:
    """varchar(max) translates to plain varchar in Postgres — no length limit."""
    long_text = "x" * 100_000
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
            "matter_description, matter_status, matter_type, open_date, "
            "created_at, updated_at, source_system) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)",
            ("m_test", "CM-1", "Test", long_text, "open", "litigation", "2024-01-01", "test"),
        )
        cur.execute("SELECT length(matter_description) FROM dim_matter WHERE matter_id = %s",
                    ("m_test",))
        assert cur.fetchone()[0] == 100_000
```

- [ ] **Step 4: Run test to confirm pass**

Run: `pytest tests/unit/test_migrations_vendor_matter.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/migrations/sql tests/unit/test_migrations_vendor_matter.py
git commit -m "feat(migrations): add dim_vendor and dim_matter"
```

---

## Task 7: Timekeeper Dimension and Rate Fact (006–007)

**Files:**
- Create: `src/lina_redshift/migrations/sql/006_dim_timekeeper.sql`
- Create: `src/lina_redshift/migrations/sql/007_fact_timekeeper_rate.sql`
- Create: `tests/unit/test_migrations_timekeeper.py`

- [ ] **Step 1: Write `006_dim_timekeeper.sql`**

```sql
CREATE TABLE IF NOT EXISTS dim_timekeeper (
    timekeeper_id varchar PRIMARY KEY,
    vendor_id varchar NOT NULL,
    timekeeper_name varchar NOT NULL,
    timekeeper_email varchar,
    timekeeper_classification varchar NOT NULL,
    years_of_experience integer,
    office_city varchar,
    office_state_province varchar,
    office_country_code char(2),
    active_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE ALL
SORTKEY (vendor_id, timekeeper_id);
```

- [ ] **Step 2: Write `007_fact_timekeeper_rate.sql`**

```sql
CREATE TABLE IF NOT EXISTS fact_timekeeper_rate (
    rate_id varchar PRIMARY KEY,
    timekeeper_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    matter_id varchar,
    rate_type varchar NOT NULL,
    hourly_rate decimal(18, 4) NOT NULL,
    currency_code char(3) NOT NULL,
    effective_start_date date NOT NULL,
    effective_end_date date,
    approval_status varchar NOT NULL,
    approved_by_user_id varchar,
    approved_at timestamp,
    created_at timestamp NOT NULL
)
DISTSTYLE KEY (timekeeper_id)
SORTKEY (timekeeper_id, effective_start_date);
```

- [ ] **Step 3: Write failing tests**

`tests/unit/test_migrations_timekeeper.py`:
```python
"""Verify timekeeper dimension and rate fact migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


def _columns(conn: PgConnection, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


@pytest.mark.unit
def test_dim_timekeeper_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "dim_timekeeper")
    expected = {
        "timekeeper_id", "vendor_id", "timekeeper_name", "timekeeper_email",
        "timekeeper_classification", "years_of_experience", "active_status",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_timekeeper_rate_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_timekeeper_rate")
    expected = {
        "rate_id", "timekeeper_id", "vendor_id", "matter_id", "rate_type",
        "hourly_rate", "currency_code", "effective_start_date",
        "effective_end_date", "approval_status",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_timekeeper_rate_supports_history(applied: PgConnection) -> None:
    """Two rates for the same timekeeper with non-overlapping effective ranges."""
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO fact_timekeeper_rate (rate_id, timekeeper_id, vendor_id, "
            "rate_type, hourly_rate, currency_code, effective_start_date, "
            "effective_end_date, approval_status, created_at) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP), "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
            ("r1", "tk1", "v1", "standard", 600, "USD", "2023-01-01",
             "2023-12-31", "approved",
             "r2", "tk1", "v1", "standard", 650, "USD", "2024-01-01",
             None, "approved"),
        )
        cur.execute(
            "SELECT count(*) FROM fact_timekeeper_rate WHERE timekeeper_id = 'tk1'"
        )
        assert cur.fetchone()[0] == 2
```

- [ ] **Step 4: Run test to confirm pass**

Run: `pytest tests/unit/test_migrations_timekeeper.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/migrations/sql tests/unit/test_migrations_timekeeper.py
git commit -m "feat(migrations): add dim_timekeeper and fact_timekeeper_rate"
```

---

## Task 8: Invoice and Line Item Facts (008–009)

**Files:**
- Create: `src/lina_redshift/migrations/sql/008_fact_invoice.sql`
- Create: `src/lina_redshift/migrations/sql/009_fact_invoice_line_item.sql`
- Create: `tests/unit/test_migrations_invoice.py`

- [ ] **Step 1: Write `008_fact_invoice.sql`**

```sql
CREATE TABLE IF NOT EXISTS fact_invoice (
    invoice_id varchar PRIMARY KEY,
    invoice_number varchar NOT NULL,
    matter_id varchar NOT NULL,
    client_matter_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    invoice_date date NOT NULL,
    billing_start_date date,
    billing_end_date date,
    received_date date,
    posted_date date,
    invoice_status varchar NOT NULL,
    approval_status varchar,
    currency_code char(3) NOT NULL,
    invoice_total_amount decimal(18, 2) NOT NULL,
    fee_total_amount decimal(18, 2),
    expense_total_amount decimal(18, 2),
    tax_total_amount decimal(18, 2),
    discount_total_amount decimal(18, 2),
    approved_amount decimal(18, 2),
    paid_amount decimal(18, 2),
    payment_date date,
    ledes_format varchar,
    source_file_id varchar,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE KEY (matter_id)
SORTKEY (invoice_date, vendor_id);
```

- [ ] **Step 2: Write `009_fact_invoice_line_item.sql`**

```sql
CREATE TABLE IF NOT EXISTS fact_invoice_line_item (
    invoice_line_item_id varchar PRIMARY KEY,
    invoice_id varchar NOT NULL,
    line_item_number integer NOT NULL,
    matter_id varchar NOT NULL,
    client_matter_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    timekeeper_id varchar,
    line_item_date date NOT NULL,
    line_item_type varchar NOT NULL,
    task_code varchar,
    activity_code varchar,
    expense_code varchar,
    line_item_description varchar(max),
    units decimal(18, 4),
    unit_rate decimal(18, 4),
    line_item_total_amount decimal(18, 2) NOT NULL,
    adjustment_amount decimal(18, 2),
    approved_line_amount decimal(18, 2),
    currency_code char(3) NOT NULL,
    usd_amount decimal(18, 2),
    fx_rate_to_usd decimal(18, 8),
    review_status varchar,
    billing_guideline_flag boolean,
    billing_guideline_reason varchar,
    created_at timestamp NOT NULL
)
DISTSTYLE KEY (matter_id)
SORTKEY (line_item_date, vendor_id);
```

- [ ] **Step 3: Write failing tests**

`tests/unit/test_migrations_invoice.py`:
```python
"""Verify invoice and line item fact migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


def _columns(conn: PgConnection, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


@pytest.mark.unit
def test_fact_invoice_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_invoice")
    expected = {
        "invoice_id", "invoice_number", "matter_id", "vendor_id",
        "invoice_date", "invoice_status", "currency_code",
        "invoice_total_amount", "fee_total_amount", "expense_total_amount",
        "approved_amount", "paid_amount", "ledes_format",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_invoice_line_item_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_invoice_line_item")
    expected = {
        "invoice_line_item_id", "invoice_id", "line_item_number",
        "matter_id", "vendor_id", "timekeeper_id", "line_item_date",
        "line_item_type", "task_code", "activity_code", "expense_code",
        "units", "unit_rate", "line_item_total_amount",
        "adjustment_amount", "approved_line_amount", "currency_code",
        "usd_amount", "fx_rate_to_usd", "billing_guideline_flag",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_invoice_line_item_decimal_precision(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO fact_invoice_line_item (invoice_line_item_id, invoice_id, "
            "line_item_number, matter_id, client_matter_id, vendor_id, "
            "line_item_date, line_item_type, line_item_total_amount, currency_code, "
            "fx_rate_to_usd, created_at) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)",
            ("li1", "inv1", 1, "m1", "CM-1", "v1", "2024-06-15", "fee",
             "1234.56", "USD", "1.23456789"),
        )
        cur.execute(
            "SELECT line_item_total_amount, fx_rate_to_usd FROM fact_invoice_line_item "
            "WHERE invoice_line_item_id = 'li1'"
        )
        amount, fx = cur.fetchone()
        assert str(amount) == "1234.56"
        assert str(fx) == "1.23456789"
```

- [ ] **Step 4: Run test to confirm pass**

Run: `pytest tests/unit/test_migrations_invoice.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/migrations/sql tests/unit/test_migrations_invoice.py
git commit -m "feat(migrations): add fact_invoice and fact_invoice_line_item"
```

---

## Task 9: Budget and Accrual Facts (010–011)

**Files:**
- Create: `src/lina_redshift/migrations/sql/010_fact_matter_budget.sql`
- Create: `src/lina_redshift/migrations/sql/011_fact_accrual.sql`
- Create: `tests/unit/test_migrations_budget_accrual.py`

- [ ] **Step 1: Write `010_fact_matter_budget.sql`**

```sql
CREATE TABLE IF NOT EXISTS fact_matter_budget (
    matter_budget_id varchar PRIMARY KEY,
    matter_id varchar NOT NULL,
    budget_version integer NOT NULL,
    budget_period_start_date date NOT NULL,
    budget_period_end_date date NOT NULL,
    budget_amount decimal(18, 2) NOT NULL,
    currency_code char(3) NOT NULL,
    budget_status varchar NOT NULL,
    submitted_by_user_id varchar,
    approved_by_user_id varchar,
    approved_at timestamp,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE KEY (matter_id)
SORTKEY (matter_id, budget_version);
```

- [ ] **Step 2: Write `011_fact_accrual.sql`**

```sql
CREATE TABLE IF NOT EXISTS fact_accrual (
    accrual_id varchar PRIMARY KEY,
    matter_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    accounting_period varchar NOT NULL,
    period_start_date date NOT NULL,
    period_end_date date NOT NULL,
    estimated_unbilled_amount decimal(18, 2) NOT NULL,
    currency_code char(3) NOT NULL,
    submitted_by varchar,
    submitted_at timestamp,
    accrual_status varchar NOT NULL,
    created_at timestamp NOT NULL,
    updated_at timestamp NOT NULL
)
DISTSTYLE KEY (matter_id)
SORTKEY (period_start_date, matter_id);
```

- [ ] **Step 3: Write failing tests**

`tests/unit/test_migrations_budget_accrual.py`:

```python
"""Verify budget and accrual fact migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


def _columns(conn: PgConnection, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


@pytest.mark.unit
def test_fact_matter_budget_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_matter_budget")
    expected = {
        "matter_budget_id", "matter_id", "budget_version",
        "budget_period_start_date", "budget_period_end_date",
        "budget_amount", "currency_code", "budget_status",
    }
    assert expected <= cols


@pytest.mark.unit
def test_fact_matter_budget_supports_versions(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO fact_matter_budget (matter_budget_id, matter_id, "
            "budget_version, budget_period_start_date, budget_period_end_date, "
            "budget_amount, currency_code, budget_status, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP), "
            "(%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
            ("b1", "m1", 1, "2024-01-01", "2024-12-31", 100000, "USD", "approved",
             "b2", "m1", 2, "2024-01-01", "2024-12-31", 150000, "USD", "revised"),
        )
        cur.execute(
            "SELECT count(*) FROM fact_matter_budget WHERE matter_id = 'm1'"
        )
        assert cur.fetchone()[0] == 2


@pytest.mark.unit
def test_fact_accrual_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "fact_accrual")
    expected = {
        "accrual_id", "matter_id", "vendor_id", "accounting_period",
        "period_start_date", "period_end_date", "estimated_unbilled_amount",
        "currency_code", "accrual_status",
    }
    assert expected <= cols
```

- [ ] **Step 4: Run test to confirm pass**

Run: `pytest tests/unit/test_migrations_budget_accrual.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/migrations/sql tests/unit/test_migrations_budget_accrual.py
git commit -m "feat(migrations): add fact_matter_budget and fact_accrual"
```

---

## Task 10: Bridge Tables (012–014)

**Files:**
- Create: `src/lina_redshift/migrations/sql/012_bridge_matter_vendor.sql`
- Create: `src/lina_redshift/migrations/sql/013_bridge_matter_person.sql`
- Create: `src/lina_redshift/migrations/sql/014_bridge_matter_allocation.sql`
- Create: `tests/unit/test_migrations_bridges.py`

- [ ] **Step 1: Write `012_bridge_matter_vendor.sql`**

```sql
CREATE TABLE IF NOT EXISTS bridge_matter_vendor (
    matter_id varchar NOT NULL,
    vendor_id varchar NOT NULL,
    vendor_role varchar NOT NULL,
    engagement_start_date date,
    engagement_end_date date,
    active_flag boolean NOT NULL,
    PRIMARY KEY (matter_id, vendor_id, vendor_role)
)
DISTSTYLE KEY (matter_id)
SORTKEY (matter_id, vendor_id);
```

- [ ] **Step 2: Write `013_bridge_matter_person.sql`**

```sql
CREATE TABLE IF NOT EXISTS bridge_matter_person (
    matter_id varchar NOT NULL,
    person_id varchar NOT NULL,
    person_source varchar NOT NULL,
    person_role varchar NOT NULL,
    start_date date,
    end_date date,
    active_flag boolean NOT NULL,
    PRIMARY KEY (matter_id, person_id, person_source, person_role)
)
DISTSTYLE KEY (matter_id)
SORTKEY (matter_id, person_source);
```

- [ ] **Step 3: Write `014_bridge_matter_allocation.sql`**

```sql
CREATE TABLE IF NOT EXISTS bridge_matter_allocation (
    matter_id varchar NOT NULL,
    legal_entity_id varchar,
    cost_center_id varchar,
    gl_account varchar,
    allocation_percentage decimal(9, 6) NOT NULL,
    effective_start_date date NOT NULL,
    effective_end_date date,
    active_flag boolean NOT NULL,
    PRIMARY KEY (matter_id, legal_entity_id, cost_center_id, gl_account, effective_start_date)
)
DISTSTYLE KEY (matter_id)
SORTKEY (matter_id, effective_start_date);
```

Note: `legal_entity_id`, `cost_center_id`, `gl_account` are nullable per the spec but appear in the composite PRIMARY KEY. Postgres treats `NULL` values in composite primary keys as distinct from each other (unlike most uniqueness constraints), which actually matches the spec's intent — null allocation columns mean "applies broadly," and multiple such rows for the same matter_id should be permitted. Redshift permits the same shape.

- [ ] **Step 4: Write failing tests**

`tests/unit/test_migrations_bridges.py`:

```python
"""Verify bridge table migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


def _columns(conn: PgConnection, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


@pytest.mark.unit
def test_bridge_matter_vendor_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "bridge_matter_vendor")
    assert {"matter_id", "vendor_id", "vendor_role", "active_flag"} <= cols


@pytest.mark.unit
def test_bridge_matter_vendor_composite_key(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO bridge_matter_vendor (matter_id, vendor_id, vendor_role, active_flag) "
            "VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)",
            ("m1", "v1", "primary_counsel", True,
             "m1", "v1", "local_counsel", True),
        )
        cur.execute(
            "SELECT count(*) FROM bridge_matter_vendor "
            "WHERE matter_id='m1' AND vendor_id='v1'"
        )
        assert cur.fetchone()[0] == 2


@pytest.mark.unit
def test_bridge_matter_person_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "bridge_matter_person")
    assert {"matter_id", "person_id", "person_source", "person_role", "active_flag"} <= cols


@pytest.mark.unit
def test_bridge_matter_allocation_columns(applied: PgConnection) -> None:
    cols = _columns(applied, "bridge_matter_allocation")
    expected = {
        "matter_id", "legal_entity_id", "cost_center_id", "gl_account",
        "allocation_percentage", "effective_start_date", "effective_end_date",
        "active_flag",
    }
    assert expected <= cols


@pytest.mark.unit
def test_bridge_matter_allocation_decimal_precision(applied: PgConnection) -> None:
    """allocation_percentage is decimal(9,6) — 99.999999% upper bound."""
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO bridge_matter_allocation (matter_id, legal_entity_id, "
            "cost_center_id, gl_account, allocation_percentage, "
            "effective_start_date, active_flag) VALUES "
            "(%s, %s, %s, %s, %s, %s, %s)",
            ("m1", "le_us", "cc_eng", "GL-1234", "0.333333", "2024-01-01", True),
        )
        cur.execute(
            "SELECT allocation_percentage FROM bridge_matter_allocation "
            "WHERE matter_id='m1'"
        )
        assert str(cur.fetchone()[0]) == "0.333333"
```

- [ ] **Step 5: Run test to confirm pass**

Run: `pytest tests/unit/test_migrations_bridges.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/migrations/sql tests/unit/test_migrations_bridges.py
git commit -m "feat(migrations): add bridge tables (matter_vendor, matter_person, matter_allocation)"
```

---

## Task 11: View and Materialized Views (015–018)

**Files:**
- Create: `src/lina_redshift/migrations/sql/015_vw_matter_current.sql`
- Create: `src/lina_redshift/migrations/sql/016_mv_matter_spend_summary.sql`
- Create: `src/lina_redshift/migrations/sql/017_mv_vendor_spend_summary.sql`
- Create: `src/lina_redshift/migrations/sql/018_mv_timekeeper_rate_analysis.sql`
- Create: `tests/unit/test_migrations_views.py`

- [ ] **Step 1: Write `015_vw_matter_current.sql`**

```sql
CREATE OR REPLACE VIEW vw_matter_current AS
SELECT
    matter_id,
    client_matter_id,
    matter_name,
    matter_status,
    matter_type,
    practice_area,
    area_of_law_code,
    open_date,
    close_date,
    matter_owner_user_id,
    lead_inhouse_counsel_user_id,
    business_unit,
    cost_center_id,
    budget_amount,
    budget_currency_code
FROM dim_matter
WHERE matter_status <> 'archived';
```

- [ ] **Step 2: Write `016_mv_matter_spend_summary.sql`**

```sql
CREATE MATERIALIZED VIEW mv_matter_spend_summary AS
SELECT
    li.matter_id,
    to_char(li.line_item_date, 'YYYY-"Q"Q') AS fiscal_period,
    sum(li.line_item_total_amount) AS total_billed_amount,
    sum(coalesce(li.approved_line_amount, li.line_item_total_amount)) AS total_approved_amount,
    sum(coalesce(inv.paid_amount, 0)) AS total_paid_amount,
    sum(case when li.line_item_type = 'fee' then li.line_item_total_amount else 0 end) AS fee_amount,
    sum(case when li.line_item_type = 'expense' then li.line_item_total_amount else 0 end) AS expense_amount,
    sum(coalesce(inv.tax_total_amount, 0)) AS tax_amount,
    sum(coalesce(li.adjustment_amount, 0)) AS adjustment_amount,
    count(distinct li.invoice_id) AS invoice_count,
    count(distinct li.vendor_id) AS vendor_count,
    count(distinct li.timekeeper_id) AS timekeeper_count,
    coalesce(max(b.budget_amount), 0) AS budget_amount,
    coalesce(max(b.budget_amount), 0) - sum(coalesce(li.approved_line_amount, li.line_item_total_amount)) AS budget_remaining,
    case when coalesce(max(b.budget_amount), 0) > 0
         then sum(coalesce(li.approved_line_amount, li.line_item_total_amount)) / max(b.budget_amount)
         else 0
    end AS budget_utilization_percent
FROM fact_invoice_line_item li
LEFT JOIN fact_invoice inv ON li.invoice_id = inv.invoice_id
LEFT JOIN fact_matter_budget b ON li.matter_id = b.matter_id
    AND b.budget_status = 'approved'
    AND li.line_item_date BETWEEN b.budget_period_start_date AND b.budget_period_end_date
GROUP BY li.matter_id, to_char(li.line_item_date, 'YYYY-"Q"Q')
AUTO REFRESH YES;
```

- [ ] **Step 3: Write `017_mv_vendor_spend_summary.sql`**

```sql
CREATE MATERIALIZED VIEW mv_vendor_spend_summary AS
SELECT
    li.vendor_id,
    to_char(li.line_item_date, 'YYYY-"Q"Q') AS fiscal_period,
    sum(li.line_item_total_amount) AS total_billed_amount,
    sum(coalesce(li.approved_line_amount, li.line_item_total_amount)) AS total_approved_amount,
    count(distinct li.matter_id) AS matter_count,
    count(distinct li.invoice_id) AS invoice_count,
    case when sum(case when li.line_item_type = 'fee' then li.units else 0 end) > 0
         then sum(case when li.line_item_type = 'fee' then li.line_item_total_amount else 0 end)
              / sum(case when li.line_item_type = 'fee' then li.units else 0 end)
         else 0
    end AS average_hourly_rate,
    sum(case when li.line_item_type = 'fee' AND tk.timekeeper_classification = 'Partner'
             then li.units else 0 end) AS partner_hours,
    sum(case when li.line_item_type = 'fee' AND tk.timekeeper_classification = 'Associate'
             then li.units else 0 end) AS associate_hours,
    sum(case when li.line_item_type = 'expense' then li.line_item_total_amount else 0 end) AS expense_amount,
    sum(coalesce(li.adjustment_amount, 0)) AS adjustment_amount,
    sum(case when li.billing_guideline_flag then 1 else 0 end) AS billing_guideline_flag_count
FROM fact_invoice_line_item li
LEFT JOIN dim_timekeeper tk ON li.timekeeper_id = tk.timekeeper_id
GROUP BY li.vendor_id, to_char(li.line_item_date, 'YYYY-"Q"Q')
AUTO REFRESH YES;
```

- [ ] **Step 4: Write `018_mv_timekeeper_rate_analysis.sql`**

```sql
CREATE MATERIALIZED VIEW mv_timekeeper_rate_analysis AS
SELECT
    li.timekeeper_id,
    li.vendor_id,
    to_char(li.line_item_date, 'YYYY-"Q"Q') AS fiscal_period,
    sum(li.units) AS billed_hours,
    sum(li.line_item_total_amount) AS billed_amount,
    case when sum(li.units) > 0
         then sum(li.line_item_total_amount) / sum(li.units)
         else 0
    end AS average_billed_rate,
    max(r.hourly_rate) AS approved_rate,
    sum(li.line_item_total_amount)
        - (max(r.hourly_rate) * sum(li.units)) AS rate_variance_amount,
    case when max(r.hourly_rate) > 0 AND sum(li.units) > 0
         then (sum(li.line_item_total_amount) - (max(r.hourly_rate) * sum(li.units)))
              / (max(r.hourly_rate) * sum(li.units))
         else 0
    end AS rate_variance_percent
FROM fact_invoice_line_item li
LEFT JOIN fact_timekeeper_rate r ON li.timekeeper_id = r.timekeeper_id
    AND r.approval_status = 'approved'
    AND li.line_item_date BETWEEN r.effective_start_date
        AND coalesce(r.effective_end_date, DATE '9999-12-31')
WHERE li.line_item_type = 'fee' AND li.timekeeper_id IS NOT NULL
GROUP BY li.timekeeper_id, li.vendor_id, to_char(li.line_item_date, 'YYYY-"Q"Q')
AUTO REFRESH YES;
```

- [ ] **Step 5: Write failing tests**

`tests/unit/test_migrations_views.py`:

```python
"""Verify view and materialized view migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


@pytest.mark.unit
def test_vw_matter_current_exists(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.views WHERE table_name = 'vw_matter_current'"
        )
        assert cur.fetchone()[0] == 1


@pytest.mark.unit
def test_vw_matter_current_filters_archived(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
            "matter_status, matter_type, open_date, created_at, updated_at, source_system) "
            "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s), "
            "(%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)",
            ("m_open", "CM-1", "Open Matter", "open", "litigation", "2024-01-01", "test",
             "m_archived", "CM-2", "Archived", "archived", "advisory", "2020-01-01", "test"),
        )
        applied.commit()
        cur.execute("SELECT matter_id FROM vw_matter_current ORDER BY matter_id")
        assert [r[0] for r in cur.fetchall()] == ["m_open"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "mv_name",
    ["mv_matter_spend_summary", "mv_vendor_spend_summary", "mv_timekeeper_rate_analysis"],
)
def test_materialized_view_exists(applied: PgConnection, mv_name: str) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pg_matviews WHERE matviewname = %s", (mv_name,)
        )
        assert cur.fetchone()[0] == 1


@pytest.mark.unit
def test_mv_matter_spend_summary_columns(applied: PgConnection) -> None:
    with applied.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'mv_matter_spend_summary'"
        )
        cols = {r[0] for r in cur.fetchall()}
    expected = {
        "matter_id", "fiscal_period", "total_billed_amount", "total_approved_amount",
        "total_paid_amount", "fee_amount", "expense_amount", "tax_amount",
        "adjustment_amount", "invoice_count", "vendor_count", "timekeeper_count",
        "budget_amount", "budget_remaining", "budget_utilization_percent",
    }
    assert expected <= cols
```

- [ ] **Step 6: Run test to confirm pass**

Run: `pytest tests/unit/test_migrations_views.py -v`
Expected: 6 passed (3 parametrized + 3 named).

- [ ] **Step 7: Run the full unit suite to confirm no regressions**

Run: `pytest -v`
Expected: all migration + dialect + connection tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/lina_redshift/migrations/sql tests/unit/test_migrations_views.py
git commit -m "feat(migrations): add vw_matter_current and three materialized views"
```

---

## Task 12: CallerContext, Errors, ResultPacket

**Files:**
- Create: `src/lina_redshift/caller.py`
- Create: `src/lina_redshift/errors.py`
- Create: `src/lina_redshift/packet.py`
- Create: `tests/unit/test_caller.py`
- Create: `tests/unit/test_packet.py`

- [ ] **Step 1: Write failing tests for `CallerContext`**

`tests/unit/test_caller.py`:

```python
"""Unit tests for CallerContext."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lina_redshift.caller import CallerContext


@pytest.mark.unit
def test_valid_caller() -> None:
    c = CallerContext(
        user_id="user_jane",
        roles=frozenset({"legal_ops"}),
        request_id="req_1",
    )
    assert c.user_id == "user_jane"
    assert "legal_ops" in c.roles
    assert c.permission_tags == frozenset()


@pytest.mark.unit
def test_caller_rejects_empty_user_id() -> None:
    with pytest.raises(ValidationError):
        CallerContext(user_id="", roles=frozenset({"legal_ops"}), request_id="req_1")


@pytest.mark.unit
def test_caller_rejects_empty_roles() -> None:
    with pytest.raises(ValidationError):
        CallerContext(user_id="user_jane", roles=frozenset(), request_id="req_1")


@pytest.mark.unit
def test_caller_role_intersection() -> None:
    c = CallerContext(
        user_id="user_jane",
        roles=frozenset({"legal_ops", "finance"}),
        request_id="req_1",
    )
    assert c.has_any_role(frozenset({"legal_ops"}))
    assert c.has_any_role(frozenset({"finance", "rate_admin"}))
    assert not c.has_any_role(frozenset({"rate_admin"}))


@pytest.mark.unit
def test_caller_wildcard_template_admits_any_role() -> None:
    """Templates with allowed_roles == {'*'} accept any non-empty role set."""
    c = CallerContext(
        user_id="user_jane",
        roles=frozenset({"some_arbitrary_role"}),
        request_id="req_1",
    )
    assert c.has_any_role(frozenset({"*"}))
```

- [ ] **Step 2: Write failing tests for errors and packet**

`tests/unit/test_packet.py`:

```python
"""Unit tests for ResultPacket and error mapping."""

from __future__ import annotations

import json

import pytest

from lina_redshift.errors import (
    AuthorizationError,
    InvalidParametersError,
    UnknownTemplateError,
    WorkerInternalError,
)
from lina_redshift.packet import ErrorPacket, ResultPacket


@pytest.mark.unit
def test_result_packet_serializes_with_schema_alias() -> None:
    p = ResultPacket(
        result_type="matter_lookup",
        metrics=[{"matter_id": "m1"}],
        sql_trace_id="01HZX0",
        row_count=1,
        truncated=False,
    )
    data = p.model_dump(by_alias=True)

    assert data["source_engine"] == "redshift"
    assert data["schema"] == "legal_matter_spend"  # aliased from schema_name
    assert data["result_type"] == "matter_lookup"
    assert data["sql_trace_id"] == "01HZX0"
    assert data["truncated"] is False


@pytest.mark.unit
def test_result_packet_round_trip_json() -> None:
    p = ResultPacket(
        result_type="matter_spend_summary",
        metrics=[{"matter_id": "m1", "fiscal_period": "2024-Q1"}],
        sql_trace_id="01HZX0",
        row_count=1,
        truncated=True,
    )
    raw = p.model_dump_json(by_alias=True)
    parsed = json.loads(raw)
    assert parsed["truncated"] is True
    assert parsed["row_count"] == 1


@pytest.mark.unit
def test_error_packet_shape() -> None:
    err = ErrorPacket.from_exception(
        AuthorizationError("missing role 'finance'"),
        sql_trace_id="01HZX0",
        result_type="vendor_spend_summary",
    )
    data = err.model_dump(by_alias=True)
    assert data["source_engine"] == "redshift"
    assert data["error"]["type"] == "AuthorizationError"
    assert "finance" in data["error"]["message"]
    assert data["sql_trace_id"] == "01HZX0"


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc,expected_type",
    [
        (UnknownTemplateError("bad"), "UnknownTemplateError"),
        (AuthorizationError("nope"), "AuthorizationError"),
        (InvalidParametersError("bad params"), "InvalidParametersError"),
        (WorkerInternalError("boom"), "WorkerInternalError"),
    ],
)
def test_error_packet_maps_each_exception_type(
    exc: Exception, expected_type: str,
) -> None:
    err = ErrorPacket.from_exception(exc, sql_trace_id="t", result_type="x")
    assert err.error.type == expected_type
```

- [ ] **Step 3: Run tests to confirm failure**

Run: `pytest tests/unit/test_caller.py tests/unit/test_packet.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 4: Implement `errors.py`**

`src/lina_redshift/errors.py`:

```python
"""Typed exceptions raised by the Redshift worker."""

from __future__ import annotations


class WorkerError(Exception):
    """Base class for worker exceptions caught at the boundary."""


class UnknownTemplateError(WorkerError):
    """Raised when a query_type does not match any registered template."""


class AuthorizationError(WorkerError):
    """Raised when the caller lacks any role required by the template."""


class InvalidParametersError(WorkerError):
    """Raised when the parameters fail pydantic validation."""


class QueryTimeoutError(WorkerError):
    """Raised when statement_timeout is reached during execution."""


class RedshiftConnectionError(WorkerError):
    """Raised on driver-level connection failure."""


class WorkerInternalError(WorkerError):
    """Raised on any other internal failure; logged with sql_trace_id."""
```

- [ ] **Step 5: Implement `caller.py`**

`src/lina_redshift/caller.py`:

```python
"""CallerContext model — identity supplied by Subsystem D to every worker call."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class CallerContext(BaseModel):
    user_id: Annotated[str, Field(min_length=1)]
    roles: frozenset[str]
    permission_tags: frozenset[str] = frozenset()
    request_id: Annotated[str, Field(min_length=1)]

    model_config = {"frozen": True}

    @field_validator("roles")
    @classmethod
    def _roles_non_empty(cls, v: frozenset[str]) -> frozenset[str]:
        if not v:
            raise ValueError("CallerContext.roles must contain at least one role")
        return v

    def has_any_role(self, allowed: frozenset[str]) -> bool:
        """Return True if the caller satisfies the template's allowed_roles.

        The wildcard sentinel {"*"} means "open to any caller with at least one role".
        """
        if "*" in allowed:
            return True
        return bool(self.roles & allowed)
```

- [ ] **Step 6: Implement `packet.py`**

`src/lina_redshift/packet.py`:

```python
"""ResultPacket and ErrorPacket — normalized worker output shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResultPacket(BaseModel):
    source_engine: Literal["redshift"] = "redshift"
    schema_name: Literal["legal_matter_spend"] = Field(
        default="legal_matter_spend", alias="schema",
    )
    result_type: str
    metrics: list[dict[str, Any]]
    sql_trace_id: str
    row_count: int
    truncated: bool = False

    model_config = {"populate_by_name": True}


class _ErrorBody(BaseModel):
    type: str
    message: str


class ErrorPacket(BaseModel):
    source_engine: Literal["redshift"] = "redshift"
    schema_name: Literal["legal_matter_spend"] = Field(
        default="legal_matter_spend", alias="schema",
    )
    result_type: str
    sql_trace_id: str
    error: _ErrorBody

    model_config = {"populate_by_name": True}

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        sql_trace_id: str,
        result_type: str,
    ) -> "ErrorPacket":
        return cls(
            result_type=result_type,
            sql_trace_id=sql_trace_id,
            error=_ErrorBody(type=type(exc).__name__, message=str(exc)),
        )
```

- [ ] **Step 7: Run tests to confirm pass**

Run: `pytest tests/unit/test_caller.py tests/unit/test_packet.py -v`
Expected: 5 + 7 = 12 passed.

- [ ] **Step 8: Run mypy and ruff**

Run: `mypy && ruff check src tests`
Expected: both exit 0.

- [ ] **Step 9: Commit**

```bash
git add src/lina_redshift/caller.py src/lina_redshift/errors.py src/lina_redshift/packet.py tests/unit/test_caller.py tests/unit/test_packet.py
git commit -m "feat(worker): add CallerContext, typed exceptions, and ResultPacket models"
```

---

## Task 13: QueryTemplate Base + AST Validator

**Files:**
- Create: `src/lina_redshift/templates/__init__.py`
- Create: `src/lina_redshift/templates/base.py`
- Create: `tests/unit/test_template_validation.py`

- [ ] **Step 1: Write failing tests for the AST validator**

`tests/unit/test_template_validation.py`:

```python
"""Unit tests for the template AST sanity checker."""

from __future__ import annotations

import pytest

from lina_redshift.templates.base import (
    APPROVED_RELATIONS,
    ALLOWED_FUNCTIONS,
    TemplateValidationError,
    validate_template_sql,
)


@pytest.mark.unit
def test_select_from_approved_relation_passes() -> None:
    sql = "SELECT matter_id FROM vw_matter_current LIMIT :limit"
    validate_template_sql(sql)  # should not raise


@pytest.mark.unit
def test_unapproved_relation_rejected() -> None:
    sql = "SELECT * FROM dim_matter LIMIT :limit"
    with pytest.raises(TemplateValidationError, match="dim_matter"):
        validate_template_sql(sql)


@pytest.mark.unit
@pytest.mark.parametrize("relation", sorted(APPROVED_RELATIONS))
def test_each_approved_relation_passes(relation: str) -> None:
    sql = f"SELECT * FROM {relation} LIMIT :limit"
    validate_template_sql(sql)


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_sql,expected_substring",
    [
        ("INSERT INTO vw_matter_current VALUES (1)", "INSERT"),
        ("UPDATE vw_matter_current SET matter_id = 'x'", "UPDATE"),
        ("DELETE FROM vw_matter_current WHERE 1=1", "DELETE"),
        ("CREATE TABLE x (id int)", "CREATE"),
        ("DROP TABLE vw_matter_current", "DROP"),
        ("TRUNCATE vw_matter_current", "TRUNCATE"),
        ("UNLOAD ('SELECT 1') TO 's3://x'", "UNLOAD"),
        ("MERGE INTO vw_matter_current USING x", "MERGE"),
    ],
)
def test_non_select_statements_rejected(bad_sql: str, expected_substring: str) -> None:
    with pytest.raises(TemplateValidationError, match=expected_substring):
        validate_template_sql(bad_sql)


@pytest.mark.unit
def test_disallowed_function_rejected() -> None:
    sql = "SELECT pg_sleep(10) FROM vw_matter_current LIMIT :limit"
    with pytest.raises(TemplateValidationError, match="pg_sleep"):
        validate_template_sql(sql)


@pytest.mark.unit
@pytest.mark.parametrize("fn", sorted(ALLOWED_FUNCTIONS))
def test_each_allowed_function_passes(fn: str) -> None:
    sql = f"SELECT {fn}(line_item_total_amount) FROM fact_invoice_line_item LIMIT :limit"
    validate_template_sql(sql)


@pytest.mark.unit
def test_missing_limit_rejected() -> None:
    sql = "SELECT matter_id FROM vw_matter_current"
    with pytest.raises(TemplateValidationError, match="LIMIT"):
        validate_template_sql(sql)


@pytest.mark.unit
def test_join_in_template_rejected() -> None:
    sql = (
        "SELECT v.matter_id, m.matter_name FROM vw_matter_current m "
        "JOIN fact_invoice v ON v.matter_id = m.matter_id LIMIT :limit"
    )
    with pytest.raises(TemplateValidationError, match="join"):
        validate_template_sql(sql)
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_template_validation.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `templates/__init__.py`**

`src/lina_redshift/templates/__init__.py`:

```python
"""Typed catalog of read-only query templates.

Importing this module triggers AST validation of every registered template.
"""

from __future__ import annotations

from lina_redshift.templates.base import QueryTemplate

# Registry is populated by register_template_module() below.
TEMPLATE_REGISTRY: dict[str, QueryTemplate] = {}


def register(template: QueryTemplate) -> QueryTemplate:
    """Register a template instance and run its AST sanity check."""
    if template.query_type in TEMPLATE_REGISTRY:
        raise ValueError(f"duplicate query_type: {template.query_type}")
    template.validate_at_import()
    TEMPLATE_REGISTRY[template.query_type] = template
    return template


def get_template(query_type: str) -> QueryTemplate:
    from lina_redshift.errors import UnknownTemplateError

    try:
        return TEMPLATE_REGISTRY[query_type]
    except KeyError as exc:
        raise UnknownTemplateError(f"no template registered for {query_type!r}") from exc


def all_templates() -> list[QueryTemplate]:
    return list(TEMPLATE_REGISTRY.values())
```

- [ ] **Step 4: Implement `templates/base.py`**

`src/lina_redshift/templates/base.py`:

```python
"""QueryTemplate ABC and the at-import AST sanity checker."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import sqlglot
from pydantic import BaseModel
from sqlglot import exp

APPROVED_RELATIONS: frozenset[str] = frozenset({
    "vw_matter_current",
    "mv_matter_spend_summary",
    "mv_vendor_spend_summary",
    "mv_timekeeper_rate_analysis",
    "fact_invoice",
    "fact_invoice_line_item",
})

ALLOWED_FUNCTIONS: frozenset[str] = frozenset({
    "sum", "count", "avg", "min", "max",
    "coalesce", "nullif",
    "to_char", "date_trunc", "extract",
    "abs", "round", "greatest", "least",
})


class TemplateValidationError(RuntimeError):
    """Raised when a template's SQL violates the spec §13 rules."""


_BANNED_TOKEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|UNLOAD|COPY)\b",
    flags=re.IGNORECASE,
)


def validate_template_sql(sql: str) -> None:
    """Run the AST sanity checks for spec §13 rules 1, 2, 5, 6, 10, 11, 12, 13.

    Rules 3, 4, 7, 8, 9 are enforced at runtime in the worker, not here.
    """
    # Rule 10/11/12: regex-level token sanity check before parsing.
    banned = _BANNED_TOKEN_RE.search(sql)
    if banned:
        raise TemplateValidationError(
            f"SQL contains banned token {banned.group(0)!r}: {sql!r}"
        )

    # Parse with Redshift dialect to be permissive of Redshift-specific syntax.
    try:
        statements = sqlglot.parse(sql, read="redshift")
    except sqlglot.errors.ParseError as exc:
        raise TemplateValidationError(f"could not parse SQL: {exc}") from exc

    if len(statements) != 1 or statements[0] is None:
        raise TemplateValidationError("template SQL must be exactly one SELECT statement")

    tree = statements[0]

    # Rule 1: must be a SELECT.
    if not isinstance(tree, exp.Select) and not (
        isinstance(tree, exp.Subqueryable) and isinstance(tree, exp.Select)
    ):
        # SELECT statements are exp.Select. Anything else fails.
        if tree.key.lower() != "select":
            raise TemplateValidationError(
                f"only SELECT statements are allowed; got {tree.key}"
            )

    # Rule 2: every referenced table must be in APPROVED_RELATIONS.
    for table in tree.find_all(exp.Table):
        name = table.name
        if name not in APPROVED_RELATIONS:
            raise TemplateValidationError(
                f"relation {name!r} is not in APPROVED_RELATIONS"
            )

    # Rule 5: no FROM-clause joins in template SQL (joins live inside MVs).
    for join in tree.find_all(exp.Join):
        raise TemplateValidationError(
            f"template must not contain join clauses; found {join.sql(dialect='redshift')!r}"
        )

    # Rule 13: every function call must be in ALLOWED_FUNCTIONS.
    for func in tree.find_all(exp.Func):
        fn_name = (func.sql_name() or func.key).lower()
        if fn_name not in ALLOWED_FUNCTIONS:
            raise TemplateValidationError(
                f"function {fn_name!r} is not in ALLOWED_FUNCTIONS"
            )

    # Rule 6: must contain a LIMIT clause (parameter binding allowed).
    if not tree.args.get("limit"):
        raise TemplateValidationError("template SQL must contain a LIMIT clause")


class QueryTemplate(ABC):
    query_type: ClassVar[str]
    allowed_roles: ClassVar[frozenset[str]]
    Params: ClassVar[type[BaseModel]]
    default_limit: ClassVar[int]
    max_limit: ClassVar[int]
    template_version: ClassVar[str]

    @abstractmethod
    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        """Return (sql_with_named_binds, parameter_dict)."""

    @abstractmethod
    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Project rows to the template's allowlisted columns."""

    def validate_at_import(self) -> None:
        """Run AST sanity check against a representative SQL produced by build_sql."""
        params = self.Params.model_construct()
        sql, _binds = self.build_sql(params)
        validate_template_sql(sql)
```

- [ ] **Step 5: Run tests to confirm pass**

Run: `pytest tests/unit/test_template_validation.py -v`
Expected: tests for each approved relation and each allowed function pass; banned tokens rejected; missing LIMIT rejected; joins rejected.

- [ ] **Step 6: Run mypy and ruff**

Run: `mypy && ruff check src tests`
Expected: both exit 0.

- [ ] **Step 7: Commit**

```bash
git add src/lina_redshift/templates tests/unit/test_template_validation.py
git commit -m "feat(templates): add QueryTemplate base and AST sanity checker"
```

---

## Task 14: Template — `matter_lookup`

**Files:**
- Create: `src/lina_redshift/templates/matter_lookup.py`
- Create: `tests/unit/test_template_matter_lookup.py`
- Modify: `src/lina_redshift/templates/__init__.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_template_matter_lookup.py`:

```python
"""Unit tests for the matter_lookup template."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lina_redshift.templates.matter_lookup import (
    MatterLookupParams,
    MatterLookupTemplate,
)


@pytest.fixture
def template() -> MatterLookupTemplate:
    return MatterLookupTemplate()


@pytest.mark.unit
def test_params_accepts_matter_id() -> None:
    p = MatterLookupParams(matter_id="m1")
    assert p.matter_id == "m1"
    assert p.client_matter_id is None


@pytest.mark.unit
def test_params_requires_exactly_one_lookup_field() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        MatterLookupParams()
    with pytest.raises(ValidationError, match="exactly one"):
        MatterLookupParams(matter_id="m1", client_matter_id="CM-1")


@pytest.mark.unit
def test_build_sql_by_matter_id(template: MatterLookupTemplate) -> None:
    params = MatterLookupParams(matter_id="m1")
    sql, binds = template.build_sql(params)
    assert "vw_matter_current" in sql
    assert "matter_id = %(matter_id)s" in sql
    assert binds == {"matter_id": "m1", "limit": template.default_limit}


@pytest.mark.unit
def test_build_sql_by_client_matter_id(template: MatterLookupTemplate) -> None:
    params = MatterLookupParams(client_matter_id="CM-1")
    sql, binds = template.build_sql(params)
    assert "client_matter_id = %(client_matter_id)s" in sql
    assert binds["client_matter_id"] == "CM-1"


@pytest.mark.unit
def test_build_sql_by_owner(template: MatterLookupTemplate) -> None:
    params = MatterLookupParams(matter_owner_user_id="user_jane")
    sql, binds = template.build_sql(params)
    assert "matter_owner_user_id = %(matter_owner_user_id)s" in sql
    assert binds["matter_owner_user_id"] == "user_jane"


@pytest.mark.unit
def test_shape_packet_projects_allowlisted_columns(template: MatterLookupTemplate) -> None:
    rows = [
        {"matter_id": "m1", "matter_name": "X", "secret_field": "leak"},
    ]
    out = template.shape_packet(rows)
    assert out[0]["matter_id"] == "m1"
    assert "secret_field" not in out[0]


@pytest.mark.unit
def test_template_metadata(template: MatterLookupTemplate) -> None:
    assert template.query_type == "matter_lookup"
    assert template.allowed_roles == frozenset({"*"})
    assert template.default_limit > 0
    assert template.max_limit >= template.default_limit
    assert template.template_version
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_template_matter_lookup.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `matter_lookup.py`**

`src/lina_redshift/templates/matter_lookup.py`:

```python
"""matter_lookup template — single-matter lookup over vw_matter_current."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

from lina_redshift.templates.base import QueryTemplate

_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({
    "matter_id", "client_matter_id", "matter_name", "matter_status",
    "matter_type", "practice_area", "area_of_law_code", "open_date",
    "close_date", "matter_owner_user_id", "lead_inhouse_counsel_user_id",
    "business_unit", "cost_center_id", "budget_amount", "budget_currency_code",
})


class MatterLookupParams(BaseModel):
    matter_id: str | None = None
    client_matter_id: str | None = None
    matter_owner_user_id: str | None = None
    include_closed: bool = False
    limit: int | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _exactly_one_lookup(self) -> "MatterLookupParams":
        provided = [
            v for v in (self.matter_id, self.client_matter_id, self.matter_owner_user_id)
            if v is not None
        ]
        if len(provided) != 1:
            raise ValueError(
                "exactly one of matter_id, client_matter_id, matter_owner_user_id is required"
            )
        return self


class MatterLookupTemplate(QueryTemplate):
    query_type: ClassVar[str] = "matter_lookup"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"*"})
    Params: ClassVar[type[BaseModel]] = MatterLookupParams
    default_limit: ClassVar[int] = 100
    max_limit: ClassVar[int] = 1_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, MatterLookupParams)
        if params.matter_id is not None:
            where = "matter_id = %(matter_id)s"
            binds: dict[str, Any] = {"matter_id": params.matter_id}
        elif params.client_matter_id is not None:
            where = "client_matter_id = %(client_matter_id)s"
            binds = {"client_matter_id": params.client_matter_id}
        else:
            where = "matter_owner_user_id = %(matter_owner_user_id)s"
            binds = {"matter_owner_user_id": params.matter_owner_user_id}

        if not params.include_closed:
            where = f"({where}) AND matter_status <> 'closed'"

        effective_limit = min(params.limit or self.default_limit, self.max_limit)
        binds["limit"] = effective_limit

        sql = (
            "SELECT matter_id, client_matter_id, matter_name, matter_status, "
            "matter_type, practice_area, area_of_law_code, open_date, close_date, "
            "matter_owner_user_id, lead_inhouse_counsel_user_id, business_unit, "
            "cost_center_id, budget_amount, budget_currency_code "
            f"FROM vw_matter_current WHERE {where} LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
```

- [ ] **Step 4: Adjust `validate_at_import` to handle conditional WHERE**

`build_sql` requires real params, but `validate_at_import` constructs an empty `MatterLookupParams` via `model_construct()`. The empty model fails the `_exactly_one_lookup` validator under `model_construct`? `model_construct` skips validators, so the model has all-None lookup fields. Calling `build_sql` then takes the `else` branch (using `matter_owner_user_id`), producing valid SQL. This is the expected behavior — `validate_at_import` only needs SQL that parses; it does not exercise real values.

- [ ] **Step 5: Register the template**

Modify `src/lina_redshift/templates/__init__.py` — append at end:

```python
from lina_redshift.templates.matter_lookup import MatterLookupTemplate

register(MatterLookupTemplate())
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/unit/test_template_matter_lookup.py tests/unit/test_template_validation.py -v`
Expected: all passing.

- [ ] **Step 7: Run full unit suite**

Run: `pytest -v`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add src/lina_redshift/templates tests/unit/test_template_matter_lookup.py
git commit -m "feat(templates): add matter_lookup template and register in catalog"
```

---

## Task 15: Template — `matter_spend_summary`

**Files:**
- Create: `src/lina_redshift/templates/matter_spend_summary.py`
- Create: `tests/unit/test_template_matter_spend_summary.py`
- Modify: `src/lina_redshift/templates/__init__.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_template_matter_spend_summary.py`:

```python
"""Unit tests for matter_spend_summary template."""

from __future__ import annotations

import pytest

from lina_redshift.templates.matter_spend_summary import (
    MatterSpendSummaryParams,
    MatterSpendSummaryTemplate,
)


@pytest.fixture
def template() -> MatterSpendSummaryTemplate:
    return MatterSpendSummaryTemplate()


@pytest.mark.unit
def test_params_default_metric_set() -> None:
    p = MatterSpendSummaryParams()
    assert "total_approved_amount" in p.metrics


@pytest.mark.unit
def test_params_rejects_unknown_metric() -> None:
    with pytest.raises(Exception):  # pydantic ValidationError on Literal
        MatterSpendSummaryParams(metrics=["bogus_metric"])  # type: ignore[list-item]


@pytest.mark.unit
def test_build_sql_no_filters(template: MatterSpendSummaryTemplate) -> None:
    sql, binds = template.build_sql(MatterSpendSummaryParams())
    assert "mv_matter_spend_summary" in sql
    assert "WHERE" not in sql.upper().split("LIMIT")[0] or "WHERE 1=1" in sql
    assert binds["limit"] == template.default_limit


@pytest.mark.unit
def test_build_sql_filters_matter_ids(template: MatterSpendSummaryTemplate) -> None:
    params = MatterSpendSummaryParams(matter_ids=["m1", "m2"])
    sql, binds = template.build_sql(params)
    assert "matter_id = ANY(%(matter_ids)s)" in sql
    assert binds["matter_ids"] == ["m1", "m2"]


@pytest.mark.unit
def test_build_sql_filters_fiscal_period(template: MatterSpendSummaryTemplate) -> None:
    params = MatterSpendSummaryParams(fiscal_periods=["2024-Q1", "2024-Q2"])
    sql, binds = template.build_sql(params)
    assert "fiscal_period = ANY(%(fiscal_periods)s)" in sql
    assert binds["fiscal_periods"] == ["2024-Q1", "2024-Q2"]


@pytest.mark.unit
def test_limit_clamped_to_max(template: MatterSpendSummaryTemplate) -> None:
    params = MatterSpendSummaryParams(limit=999_999)
    _sql, binds = template.build_sql(params)
    assert binds["limit"] == template.max_limit


@pytest.mark.unit
def test_shape_packet_projects_metrics(template: MatterSpendSummaryTemplate) -> None:
    rows = [
        {"matter_id": "m1", "fiscal_period": "2024-Q1",
         "total_approved_amount": 1000, "internal_only": "leak"},
    ]
    out = template.shape_packet(rows)
    assert out[0]["matter_id"] == "m1"
    assert "internal_only" not in out[0]


@pytest.mark.unit
def test_allowed_roles(template: MatterSpendSummaryTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance", "matter_owner"})
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_template_matter_spend_summary.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `matter_spend_summary.py`**

`src/lina_redshift/templates/matter_spend_summary.py`:

```python
"""matter_spend_summary template — fast matter-level spend metrics."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from lina_redshift.templates.base import QueryTemplate

MetricName = Literal[
    "total_billed_amount", "total_approved_amount", "total_paid_amount",
    "fee_amount", "expense_amount", "tax_amount", "adjustment_amount",
    "invoice_count", "vendor_count", "timekeeper_count",
    "budget_amount", "budget_remaining", "budget_utilization_percent",
]

_ALL_METRICS: list[MetricName] = list(MetricName.__args__)  # type: ignore[attr-defined]
_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({"matter_id", "fiscal_period", *_ALL_METRICS})


class MatterSpendSummaryParams(BaseModel):
    matter_ids: list[str] | None = None
    fiscal_periods: list[str] | None = None
    metrics: list[MetricName] = Field(default_factory=lambda: list(_ALL_METRICS))
    limit: int | None = None

    model_config = {"frozen": True}


class MatterSpendSummaryTemplate(QueryTemplate):
    query_type: ClassVar[str] = "matter_spend_summary"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"legal_ops", "finance", "matter_owner"})
    Params: ClassVar[type[BaseModel]] = MatterSpendSummaryParams
    default_limit: ClassVar[int] = 500
    max_limit: ClassVar[int] = 5_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, MatterSpendSummaryParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.matter_ids:
            clauses.append("matter_id = ANY(%(matter_ids)s)")
            binds["matter_ids"] = list(params.matter_ids)
        if params.fiscal_periods:
            clauses.append("fiscal_period = ANY(%(fiscal_periods)s)")
            binds["fiscal_periods"] = list(params.fiscal_periods)

        where = " AND ".join(clauses) if clauses else "1=1"
        effective_limit = min(params.limit or self.default_limit, self.max_limit)
        binds["limit"] = effective_limit

        select_cols = ["matter_id", "fiscal_period", *params.metrics]
        sql = (
            f"SELECT {', '.join(select_cols)} FROM mv_matter_spend_summary "
            f"WHERE {where} LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
```

- [ ] **Step 4: Register the template**

Append to `src/lina_redshift/templates/__init__.py`:

```python
from lina_redshift.templates.matter_spend_summary import MatterSpendSummaryTemplate

register(MatterSpendSummaryTemplate())
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_template_matter_spend_summary.py -v`
Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/templates tests/unit/test_template_matter_spend_summary.py
git commit -m "feat(templates): add matter_spend_summary template"
```

---

## Task 16: Template — `vendor_spend_summary`

**Files:**
- Create: `src/lina_redshift/templates/vendor_spend_summary.py`
- Create: `tests/unit/test_template_vendor_spend_summary.py`
- Modify: `src/lina_redshift/templates/__init__.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_template_vendor_spend_summary.py`:

```python
"""Unit tests for vendor_spend_summary template."""

from __future__ import annotations

import pytest

from lina_redshift.templates.vendor_spend_summary import (
    VendorSpendSummaryParams,
    VendorSpendSummaryTemplate,
)


@pytest.fixture
def template() -> VendorSpendSummaryTemplate:
    return VendorSpendSummaryTemplate()


@pytest.mark.unit
def test_params_default_metrics() -> None:
    p = VendorSpendSummaryParams()
    assert "total_approved_amount" in p.metrics
    assert "billing_guideline_flag_count" in p.metrics


@pytest.mark.unit
def test_build_sql_filters_vendor_ids(template: VendorSpendSummaryTemplate) -> None:
    sql, binds = template.build_sql(VendorSpendSummaryParams(vendor_ids=["v1", "v2"]))
    assert "mv_vendor_spend_summary" in sql
    assert "vendor_id = ANY(%(vendor_ids)s)" in sql
    assert binds["vendor_ids"] == ["v1", "v2"]


@pytest.mark.unit
def test_build_sql_filters_fiscal_period(template: VendorSpendSummaryTemplate) -> None:
    sql, binds = template.build_sql(VendorSpendSummaryParams(fiscal_periods=["2024-Q1"]))
    assert "fiscal_period = ANY(%(fiscal_periods)s)" in sql


@pytest.mark.unit
def test_shape_packet_strips_unknown_columns(template: VendorSpendSummaryTemplate) -> None:
    rows = [{"vendor_id": "v1", "total_billed_amount": 100, "leak": "x"}]
    out = template.shape_packet(rows)
    assert "leak" not in out[0]


@pytest.mark.unit
def test_allowed_roles(template: VendorSpendSummaryTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance"})
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_template_vendor_spend_summary.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `vendor_spend_summary.py`**

`src/lina_redshift/templates/vendor_spend_summary.py`:

```python
"""vendor_spend_summary template — vendor comparison and outside counsel analytics."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from lina_redshift.templates.base import QueryTemplate

MetricName = Literal[
    "total_billed_amount", "total_approved_amount",
    "matter_count", "invoice_count",
    "average_hourly_rate", "partner_hours", "associate_hours",
    "expense_amount", "adjustment_amount", "billing_guideline_flag_count",
]

_ALL_METRICS: list[MetricName] = list(MetricName.__args__)  # type: ignore[attr-defined]
_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({"vendor_id", "fiscal_period", *_ALL_METRICS})


class VendorSpendSummaryParams(BaseModel):
    vendor_ids: list[str] | None = None
    fiscal_periods: list[str] | None = None
    metrics: list[MetricName] = Field(default_factory=lambda: list(_ALL_METRICS))
    limit: int | None = None

    model_config = {"frozen": True}


class VendorSpendSummaryTemplate(QueryTemplate):
    query_type: ClassVar[str] = "vendor_spend_summary"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"legal_ops", "finance"})
    Params: ClassVar[type[BaseModel]] = VendorSpendSummaryParams
    default_limit: ClassVar[int] = 500
    max_limit: ClassVar[int] = 5_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, VendorSpendSummaryParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.vendor_ids:
            clauses.append("vendor_id = ANY(%(vendor_ids)s)")
            binds["vendor_ids"] = list(params.vendor_ids)
        if params.fiscal_periods:
            clauses.append("fiscal_period = ANY(%(fiscal_periods)s)")
            binds["fiscal_periods"] = list(params.fiscal_periods)

        where = " AND ".join(clauses) if clauses else "1=1"
        binds["limit"] = min(params.limit or self.default_limit, self.max_limit)
        select_cols = ["vendor_id", "fiscal_period", *params.metrics]
        sql = (
            f"SELECT {', '.join(select_cols)} FROM mv_vendor_spend_summary "
            f"WHERE {where} LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
```

- [ ] **Step 4: Register**

Append to `src/lina_redshift/templates/__init__.py`:

```python
from lina_redshift.templates.vendor_spend_summary import VendorSpendSummaryTemplate

register(VendorSpendSummaryTemplate())
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_template_vendor_spend_summary.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/templates tests/unit/test_template_vendor_spend_summary.py
git commit -m "feat(templates): add vendor_spend_summary template"
```

---

## Task 17: Template — `timekeeper_rate_analysis`

**Files:**
- Create: `src/lina_redshift/templates/timekeeper_rate_analysis.py`
- Create: `tests/unit/test_template_timekeeper_rate_analysis.py`
- Modify: `src/lina_redshift/templates/__init__.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_template_timekeeper_rate_analysis.py`:

```python
"""Unit tests for timekeeper_rate_analysis template."""

from __future__ import annotations

import pytest

from lina_redshift.templates.timekeeper_rate_analysis import (
    TimekeeperRateAnalysisParams,
    TimekeeperRateAnalysisTemplate,
)


@pytest.fixture
def template() -> TimekeeperRateAnalysisTemplate:
    return TimekeeperRateAnalysisTemplate()


@pytest.mark.unit
def test_params_default_threshold_is_none() -> None:
    p = TimekeeperRateAnalysisParams()
    assert p.rate_variance_threshold is None


@pytest.mark.unit
def test_build_sql_filters_vendor_ids(template: TimekeeperRateAnalysisTemplate) -> None:
    sql, binds = template.build_sql(TimekeeperRateAnalysisParams(vendor_ids=["v1"]))
    assert "mv_timekeeper_rate_analysis" in sql
    assert "vendor_id = ANY(%(vendor_ids)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_timekeeper_ids(template: TimekeeperRateAnalysisTemplate) -> None:
    sql, binds = template.build_sql(TimekeeperRateAnalysisParams(timekeeper_ids=["tk1"]))
    assert "timekeeper_id = ANY(%(timekeeper_ids)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_variance_threshold(template: TimekeeperRateAnalysisTemplate) -> None:
    sql, binds = template.build_sql(
        TimekeeperRateAnalysisParams(rate_variance_threshold=0.1)
    )
    assert "abs(rate_variance_percent) >= %(rate_variance_threshold)s" in sql
    assert binds["rate_variance_threshold"] == 0.1


@pytest.mark.unit
def test_allowed_roles(template: TimekeeperRateAnalysisTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance", "rate_admin"})
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_template_timekeeper_rate_analysis.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `timekeeper_rate_analysis.py`**

`src/lina_redshift/templates/timekeeper_rate_analysis.py`:

```python
"""timekeeper_rate_analysis — rate comparison and rate enforcement."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from lina_redshift.templates.base import QueryTemplate

_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({
    "timekeeper_id", "vendor_id", "fiscal_period",
    "billed_hours", "billed_amount", "average_billed_rate",
    "approved_rate", "rate_variance_amount", "rate_variance_percent",
})


class TimekeeperRateAnalysisParams(BaseModel):
    vendor_ids: list[str] | None = None
    timekeeper_ids: list[str] | None = None
    fiscal_periods: list[str] | None = None
    rate_variance_threshold: float | None = None
    limit: int | None = None

    model_config = {"frozen": True}


class TimekeeperRateAnalysisTemplate(QueryTemplate):
    query_type: ClassVar[str] = "timekeeper_rate_analysis"
    allowed_roles: ClassVar[frozenset[str]] = frozenset(
        {"legal_ops", "finance", "rate_admin"}
    )
    Params: ClassVar[type[BaseModel]] = TimekeeperRateAnalysisParams
    default_limit: ClassVar[int] = 500
    max_limit: ClassVar[int] = 5_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, TimekeeperRateAnalysisParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.vendor_ids:
            clauses.append("vendor_id = ANY(%(vendor_ids)s)")
            binds["vendor_ids"] = list(params.vendor_ids)
        if params.timekeeper_ids:
            clauses.append("timekeeper_id = ANY(%(timekeeper_ids)s)")
            binds["timekeeper_ids"] = list(params.timekeeper_ids)
        if params.fiscal_periods:
            clauses.append("fiscal_period = ANY(%(fiscal_periods)s)")
            binds["fiscal_periods"] = list(params.fiscal_periods)
        if params.rate_variance_threshold is not None:
            clauses.append("abs(rate_variance_percent) >= %(rate_variance_threshold)s")
            binds["rate_variance_threshold"] = params.rate_variance_threshold

        where = " AND ".join(clauses) if clauses else "1=1"
        binds["limit"] = min(params.limit or self.default_limit, self.max_limit)
        sql = (
            "SELECT timekeeper_id, vendor_id, fiscal_period, billed_hours, "
            "billed_amount, average_billed_rate, approved_rate, "
            "rate_variance_amount, rate_variance_percent "
            f"FROM mv_timekeeper_rate_analysis WHERE {where} LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
```

- [ ] **Step 4: Register**

Append to `src/lina_redshift/templates/__init__.py`:

```python
from lina_redshift.templates.timekeeper_rate_analysis import TimekeeperRateAnalysisTemplate

register(TimekeeperRateAnalysisTemplate())
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_template_timekeeper_rate_analysis.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/templates tests/unit/test_template_timekeeper_rate_analysis.py
git commit -m "feat(templates): add timekeeper_rate_analysis template"
```

---

## Task 18: Template — `invoice_search`

**Files:**
- Create: `src/lina_redshift/templates/invoice_search.py`
- Create: `tests/unit/test_template_invoice_search.py`
- Modify: `src/lina_redshift/templates/__init__.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_template_invoice_search.py`:

```python
"""Unit tests for invoice_search template."""

from __future__ import annotations

from datetime import date

import pytest

from lina_redshift.templates.invoice_search import (
    DateRange,
    InvoiceSearchParams,
    InvoiceSearchTemplate,
)


@pytest.fixture
def template() -> InvoiceSearchTemplate:
    return InvoiceSearchTemplate()


@pytest.mark.unit
def test_build_sql_filters_matter_ids(template: InvoiceSearchTemplate) -> None:
    sql, binds = template.build_sql(InvoiceSearchParams(matter_ids=["m1"]))
    assert "fact_invoice" in sql
    assert "matter_id = ANY(%(matter_ids)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_invoice_status(template: InvoiceSearchTemplate) -> None:
    sql, binds = template.build_sql(InvoiceSearchParams(invoice_status=["paid"]))
    assert "invoice_status = ANY(%(invoice_status)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_date_range(template: InvoiceSearchTemplate) -> None:
    params = InvoiceSearchParams(
        invoice_date_range=DateRange(start=date(2024, 1, 1), end=date(2024, 12, 31)),
    )
    sql, binds = template.build_sql(params)
    assert "invoice_date BETWEEN %(invoice_date_start)s AND %(invoice_date_end)s" in sql
    assert binds["invoice_date_start"] == date(2024, 1, 1)
    assert binds["invoice_date_end"] == date(2024, 12, 31)


@pytest.mark.unit
def test_build_sql_filters_amount_range(template: InvoiceSearchTemplate) -> None:
    sql, binds = template.build_sql(
        InvoiceSearchParams(min_amount=1000, max_amount=50000)
    )
    assert "invoice_total_amount >= %(min_amount)s" in sql
    assert "invoice_total_amount <= %(max_amount)s" in sql


@pytest.mark.unit
def test_allowed_roles(template: InvoiceSearchTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance", "matter_owner"})


@pytest.mark.unit
def test_shape_packet_strips_unknown(template: InvoiceSearchTemplate) -> None:
    rows = [{"invoice_id": "inv1", "invoice_total_amount": 100, "secret": "leak"}]
    out = template.shape_packet(rows)
    assert "secret" not in out[0]
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_template_invoice_search.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `invoice_search.py`**

`src/lina_redshift/templates/invoice_search.py`:

```python
"""invoice_search — filtered listing of fact_invoice rows."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, ClassVar

from pydantic import BaseModel

from lina_redshift.templates.base import QueryTemplate

_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({
    "invoice_id", "invoice_number", "matter_id", "client_matter_id",
    "vendor_id", "invoice_date", "billing_start_date", "billing_end_date",
    "invoice_status", "approval_status", "currency_code",
    "invoice_total_amount", "fee_total_amount", "expense_total_amount",
    "approved_amount", "paid_amount", "payment_date",
})


class DateRange(BaseModel):
    start: date
    end: date

    model_config = {"frozen": True}


class InvoiceSearchParams(BaseModel):
    matter_ids: list[str] | None = None
    vendor_ids: list[str] | None = None
    invoice_status: list[str] | None = None
    invoice_date_range: DateRange | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    limit: int | None = None

    model_config = {"frozen": True}


class InvoiceSearchTemplate(QueryTemplate):
    query_type: ClassVar[str] = "invoice_search"
    allowed_roles: ClassVar[frozenset[str]] = frozenset(
        {"legal_ops", "finance", "matter_owner"}
    )
    Params: ClassVar[type[BaseModel]] = InvoiceSearchParams
    default_limit: ClassVar[int] = 200
    max_limit: ClassVar[int] = 2_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, InvoiceSearchParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.matter_ids:
            clauses.append("matter_id = ANY(%(matter_ids)s)")
            binds["matter_ids"] = list(params.matter_ids)
        if params.vendor_ids:
            clauses.append("vendor_id = ANY(%(vendor_ids)s)")
            binds["vendor_ids"] = list(params.vendor_ids)
        if params.invoice_status:
            clauses.append("invoice_status = ANY(%(invoice_status)s)")
            binds["invoice_status"] = list(params.invoice_status)
        if params.invoice_date_range:
            clauses.append(
                "invoice_date BETWEEN %(invoice_date_start)s AND %(invoice_date_end)s"
            )
            binds["invoice_date_start"] = params.invoice_date_range.start
            binds["invoice_date_end"] = params.invoice_date_range.end
        if params.min_amount is not None:
            clauses.append("invoice_total_amount >= %(min_amount)s")
            binds["min_amount"] = params.min_amount
        if params.max_amount is not None:
            clauses.append("invoice_total_amount <= %(max_amount)s")
            binds["max_amount"] = params.max_amount

        where = " AND ".join(clauses) if clauses else "1=1"
        binds["limit"] = min(params.limit or self.default_limit, self.max_limit)
        sql = (
            "SELECT invoice_id, invoice_number, matter_id, client_matter_id, "
            "vendor_id, invoice_date, billing_start_date, billing_end_date, "
            "invoice_status, approval_status, currency_code, invoice_total_amount, "
            "fee_total_amount, expense_total_amount, approved_amount, paid_amount, "
            "payment_date "
            f"FROM fact_invoice WHERE {where} ORDER BY invoice_date DESC LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
```

- [ ] **Step 4: Register**

Append to `src/lina_redshift/templates/__init__.py`:

```python
from lina_redshift.templates.invoice_search import InvoiceSearchTemplate

register(InvoiceSearchTemplate())
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_template_invoice_search.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/templates tests/unit/test_template_invoice_search.py
git commit -m "feat(templates): add invoice_search template"
```

---

## Task 19: Template — `line_item_detail`

**Files:**
- Create: `src/lina_redshift/templates/line_item_detail.py`
- Create: `tests/unit/test_template_line_item_detail.py`
- Modify: `src/lina_redshift/templates/__init__.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_template_line_item_detail.py`:

```python
"""Unit tests for line_item_detail template."""

from __future__ import annotations

from datetime import date

import pytest

from lina_redshift.templates.line_item_detail import (
    LineItemDetailParams,
    LineItemDetailTemplate,
)
from lina_redshift.templates.invoice_search import DateRange


@pytest.fixture
def template() -> LineItemDetailTemplate:
    return LineItemDetailTemplate()


@pytest.mark.unit
def test_build_sql_requires_at_least_one_filter(template: LineItemDetailTemplate) -> None:
    """Detail listings must always be scoped to avoid scanning the whole fact table."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="at least one"):
        LineItemDetailParams()


@pytest.mark.unit
def test_build_sql_filters_invoice_id(template: LineItemDetailTemplate) -> None:
    sql, binds = template.build_sql(LineItemDetailParams(invoice_ids=["inv1"]))
    assert "fact_invoice_line_item" in sql
    assert "invoice_id = ANY(%(invoice_ids)s)" in sql


@pytest.mark.unit
def test_build_sql_filters_billing_guideline(template: LineItemDetailTemplate) -> None:
    params = LineItemDetailParams(
        invoice_ids=["inv1"], billing_guideline_flag=True,
    )
    sql, binds = template.build_sql(params)
    assert "billing_guideline_flag = %(billing_guideline_flag)s" in sql
    assert binds["billing_guideline_flag"] is True


@pytest.mark.unit
def test_build_sql_filters_date_range(template: LineItemDetailTemplate) -> None:
    params = LineItemDetailParams(
        matter_ids=["m1"],
        line_item_date_range=DateRange(start=date(2024, 1, 1), end=date(2024, 6, 30)),
    )
    sql, binds = template.build_sql(params)
    assert "line_item_date BETWEEN %(line_item_date_start)s AND %(line_item_date_end)s" in sql


@pytest.mark.unit
def test_allowed_roles(template: LineItemDetailTemplate) -> None:
    assert template.allowed_roles == frozenset({"legal_ops", "finance"})
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_template_line_item_detail.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `line_item_detail.py`**

`src/lina_redshift/templates/line_item_detail.py`:

```python
"""line_item_detail — line-item-grain listing with mandatory filtering."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

from lina_redshift.templates.base import QueryTemplate
from lina_redshift.templates.invoice_search import DateRange

_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset({
    "invoice_line_item_id", "invoice_id", "line_item_number",
    "matter_id", "client_matter_id", "vendor_id", "timekeeper_id",
    "line_item_date", "line_item_type", "task_code", "activity_code", "expense_code",
    "units", "unit_rate", "line_item_total_amount", "adjustment_amount",
    "approved_line_amount", "currency_code", "usd_amount",
    "review_status", "billing_guideline_flag", "billing_guideline_reason",
})


class LineItemDetailParams(BaseModel):
    invoice_ids: list[str] | None = None
    matter_ids: list[str] | None = None
    task_codes: list[str] | None = None
    expense_codes: list[str] | None = None
    billing_guideline_flag: bool | None = None
    line_item_date_range: DateRange | None = None
    limit: int | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _at_least_one_filter(self) -> "LineItemDetailParams":
        scoping = (
            self.invoice_ids, self.matter_ids, self.task_codes,
            self.expense_codes, self.line_item_date_range,
        )
        if not any(scoping):
            raise ValueError(
                "line_item_detail requires at least one scoping filter "
                "(invoice_ids, matter_ids, task_codes, expense_codes, "
                "or line_item_date_range)"
            )
        return self


class LineItemDetailTemplate(QueryTemplate):
    query_type: ClassVar[str] = "line_item_detail"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"legal_ops", "finance"})
    Params: ClassVar[type[BaseModel]] = LineItemDetailParams
    default_limit: ClassVar[int] = 500
    max_limit: ClassVar[int] = 5_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, LineItemDetailParams)
        binds: dict[str, Any] = {}
        clauses: list[str] = []
        if params.invoice_ids:
            clauses.append("invoice_id = ANY(%(invoice_ids)s)")
            binds["invoice_ids"] = list(params.invoice_ids)
        if params.matter_ids:
            clauses.append("matter_id = ANY(%(matter_ids)s)")
            binds["matter_ids"] = list(params.matter_ids)
        if params.task_codes:
            clauses.append("task_code = ANY(%(task_codes)s)")
            binds["task_codes"] = list(params.task_codes)
        if params.expense_codes:
            clauses.append("expense_code = ANY(%(expense_codes)s)")
            binds["expense_codes"] = list(params.expense_codes)
        if params.billing_guideline_flag is not None:
            clauses.append("billing_guideline_flag = %(billing_guideline_flag)s")
            binds["billing_guideline_flag"] = params.billing_guideline_flag
        if params.line_item_date_range:
            clauses.append(
                "line_item_date BETWEEN "
                "%(line_item_date_start)s AND %(line_item_date_end)s"
            )
            binds["line_item_date_start"] = params.line_item_date_range.start
            binds["line_item_date_end"] = params.line_item_date_range.end

        where = " AND ".join(clauses)
        binds["limit"] = min(params.limit or self.default_limit, self.max_limit)
        sql = (
            "SELECT invoice_line_item_id, invoice_id, line_item_number, "
            "matter_id, client_matter_id, vendor_id, timekeeper_id, "
            "line_item_date, line_item_type, task_code, activity_code, expense_code, "
            "units, unit_rate, line_item_total_amount, adjustment_amount, "
            "approved_line_amount, currency_code, usd_amount, review_status, "
            "billing_guideline_flag, billing_guideline_reason "
            f"FROM fact_invoice_line_item WHERE {where} "
            "ORDER BY line_item_date DESC LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS}
            for row in rows
        ]
```

- [ ] **Step 4: Adjust `validate_at_import` for `line_item_detail`**

`base.py`'s `validate_at_import` calls `Params.model_construct()` which bypasses validators. For `LineItemDetailParams`, that means `at_least_one_filter` is skipped — which is what we want for AST validation. The resulting empty model passes through `build_sql` and produces SQL with `WHERE ` (empty clauses → empty WHERE). That SQL won't parse cleanly under sqlglot.

To handle this without making the production code aware of "import time," override `validate_at_import` in `LineItemDetailTemplate`:

Add at the bottom of `LineItemDetailTemplate`:

```python
    def validate_at_import(self) -> None:
        """Use a minimal valid params instance (one filter) to render SQL for AST checks."""
        sample = LineItemDetailParams(invoice_ids=["sample"])
        sql, _binds = self.build_sql(sample)
        from lina_redshift.templates.base import validate_template_sql

        validate_template_sql(sql)
```

- [ ] **Step 5: Register**

Append to `src/lina_redshift/templates/__init__.py`:

```python
from lina_redshift.templates.line_item_detail import LineItemDetailTemplate

register(LineItemDetailTemplate())
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/unit/test_template_line_item_detail.py -v`
Expected: 5 passed.

- [ ] **Step 7: Run the full unit suite**

Run: `pytest -v`
Expected: all tests green; registry imports cleanly with all 6 templates AST-validated.

- [ ] **Step 8: Commit**

```bash
git add src/lina_redshift/templates tests/unit/test_template_line_item_detail.py
git commit -m "feat(templates): add line_item_detail template (mandatory scoping filter)"
```

---

## Task 20: Template Registry Smoke Tests

**Files:**
- Create: `tests/unit/test_template_registry.py`

- [ ] **Step 1: Write registry-level tests**

`tests/unit/test_template_registry.py`:

```python
"""End-to-end tests on the populated registry."""

from __future__ import annotations

import pytest

from lina_redshift.errors import UnknownTemplateError
from lina_redshift.templates import TEMPLATE_REGISTRY, all_templates, get_template


@pytest.mark.unit
def test_six_templates_registered() -> None:
    assert set(TEMPLATE_REGISTRY) == {
        "matter_lookup",
        "matter_spend_summary",
        "vendor_spend_summary",
        "timekeeper_rate_analysis",
        "invoice_search",
        "line_item_detail",
    }


@pytest.mark.unit
def test_get_template_returns_instance() -> None:
    t = get_template("matter_lookup")
    assert t.query_type == "matter_lookup"


@pytest.mark.unit
def test_get_template_raises_on_unknown() -> None:
    with pytest.raises(UnknownTemplateError, match="bogus"):
        get_template("bogus")


@pytest.mark.unit
def test_all_templates_have_unique_query_types() -> None:
    types = [t.query_type for t in all_templates()]
    assert len(types) == len(set(types))


@pytest.mark.unit
def test_all_templates_have_non_empty_allowed_roles() -> None:
    for t in all_templates():
        assert t.allowed_roles, f"{t.query_type} has empty allowed_roles"


@pytest.mark.unit
def test_all_templates_have_max_limit_at_least_default() -> None:
    for t in all_templates():
        assert t.max_limit >= t.default_limit


@pytest.mark.unit
def test_all_templates_have_template_version_string() -> None:
    for t in all_templates():
        assert isinstance(t.template_version, str)
        assert len(t.template_version) > 0
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_template_registry.py -v`
Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_template_registry.py
git commit -m "test(templates): add registry smoke tests covering all six templates"
```

---

## Task 21: Logging Configuration

**Files:**
- Create: `src/lina_redshift/logging_config.py`
- Create: `tests/unit/test_logging_config.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_logging_config.py`:

```python
"""Unit tests for logging configuration."""

from __future__ import annotations

import json
import logging
from io import StringIO

import pytest

from lina_redshift.logging_config import bind_call_context, configure_logging, get_logger


@pytest.mark.unit
def test_configure_logging_json_emits_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_LOG_FORMAT", "json")
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    configure_logging(handler=handler)

    logger = get_logger("test")
    logger.info("hello", foo="bar")

    line = buf.getvalue().strip()
    parsed = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["foo"] == "bar"


@pytest.mark.unit
def test_bind_call_context_attaches_trace_fields() -> None:
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    configure_logging(handler=handler, fmt="json")

    logger = get_logger("test")
    bound = bind_call_context(
        logger,
        sql_trace_id="01HZX0",
        request_id="req_1",
        user_id="user_jane",
        query_type="matter_lookup",
        template_version="1.0.0",
    )
    bound.info("call_start")

    parsed = json.loads(buf.getvalue().strip())
    assert parsed["sql_trace_id"] == "01HZX0"
    assert parsed["query_type"] == "matter_lookup"
```

- [ ] **Step 2: Run test to confirm failure**

Run: `pytest tests/unit/test_logging_config.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `logging_config.py`**

`src/lina_redshift/logging_config.py`:

```python
"""structlog setup with JSON renderer (prod) or console renderer (dev)."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog
from structlog.stdlib import BoundLogger


def configure_logging(*, handler: logging.Handler | None = None, fmt: str | None = None) -> None:
    chosen_fmt = (fmt or os.environ.get("LINA_LOG_FORMAT") or "console").lower()

    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
    ]
    if chosen_fmt == "json":
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler or logging.StreamHandler(sys.stderr))
    root.setLevel(logging.INFO)


def get_logger(name: str = "lina_redshift") -> BoundLogger:
    return structlog.stdlib.get_logger(name)


def bind_call_context(
    logger: BoundLogger,
    *,
    sql_trace_id: str,
    request_id: str,
    user_id: str,
    query_type: str,
    template_version: str,
) -> BoundLogger:
    return logger.bind(
        sql_trace_id=sql_trace_id,
        request_id=request_id,
        user_id=user_id,
        query_type=query_type,
        template_version=template_version,
    )
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `pytest tests/unit/test_logging_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/logging_config.py tests/unit/test_logging_config.py
git commit -m "feat(logging): add structlog config with JSON/console renderers and call context"
```

---

## Task 22: RedshiftWorker

**Files:**
- Create: `src/lina_redshift/worker.py`
- Create: `tests/unit/test_worker.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_worker.py`:

```python
"""End-to-end unit tests for RedshiftWorker against Postgres."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.caller import CallerContext
from lina_redshift.errors import (
    AuthorizationError,
    InvalidParametersError,
    UnknownTemplateError,
)
from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.packet import ErrorPacket, ResultPacket
from lina_redshift.worker import RedshiftWorker

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def worker_db(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    with pg_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
            "matter_status, matter_type, open_date, created_at, updated_at, source_system) "
            "VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)",
            ("matter_acme", "CM-1", "Acme v. Beta", "open", "litigation",
             "2024-06-01", "test"),
        )
    pg_conn.commit()
    return pg_conn


@pytest.fixture
def legal_ops_caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane",
        roles=frozenset({"legal_ops"}),
        request_id="req_1",
    )


@pytest.fixture
def matter_owner_caller() -> CallerContext:
    return CallerContext(
        user_id="user_alex",
        roles=frozenset({"matter_owner"}),
        request_id="req_2",
    )


@pytest.fixture
def unauthorized_caller() -> CallerContext:
    return CallerContext(
        user_id="user_bob",
        roles=frozenset({"random_role"}),
        request_id="req_3",
    )


@pytest.fixture
def worker(worker_db: PgConnection) -> RedshiftWorker:
    return RedshiftWorker(connection=worker_db)


@pytest.mark.unit
def test_run_returns_result_packet(worker: RedshiftWorker, legal_ops_caller: CallerContext) -> None:
    packet = worker.run(
        query_type="matter_lookup",
        params={"matter_id": "matter_acme"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 1
    assert packet.metrics[0]["matter_id"] == "matter_acme"
    assert packet.metrics[0]["matter_name"] == "Acme v. Beta"
    assert packet.sql_trace_id


@pytest.mark.unit
def test_run_unknown_template_returns_error_packet(
    worker: RedshiftWorker, legal_ops_caller: CallerContext,
) -> None:
    packet = worker.run(
        query_type="bogus",
        params={},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ErrorPacket)
    assert packet.error.type == "UnknownTemplateError"


@pytest.mark.unit
def test_run_missing_role_returns_error_packet(
    worker: RedshiftWorker, unauthorized_caller: CallerContext,
) -> None:
    packet = worker.run(
        query_type="matter_spend_summary",
        params={},
        caller=unauthorized_caller,
    )
    assert isinstance(packet, ErrorPacket)
    assert packet.error.type == "AuthorizationError"


@pytest.mark.unit
def test_run_invalid_params_returns_error_packet(
    worker: RedshiftWorker, legal_ops_caller: CallerContext,
) -> None:
    packet = worker.run(
        query_type="matter_lookup",
        params={},  # no lookup field
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ErrorPacket)
    assert packet.error.type == "InvalidParametersError"


@pytest.mark.unit
def test_run_attaches_truncated_when_max_limit_hit(
    worker_db: PgConnection, legal_ops_caller: CallerContext,
) -> None:
    """Insert enough rows to hit max_limit and verify truncated=True."""
    with worker_db.cursor() as cur:
        for i in range(1, 6):
            cur.execute(
                "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
                "matter_status, matter_type, open_date, matter_owner_user_id, "
                "created_at, updated_at, source_system) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)",
                (f"m_{i}", f"CM-{i}", f"Owned Matter {i}", "open", "litigation",
                 "2024-01-01", "user_jane", "test"),
            )
    worker_db.commit()
    worker = RedshiftWorker(connection=worker_db)
    packet = worker.run(
        query_type="matter_lookup",
        params={"matter_owner_user_id": "user_jane", "limit": 2},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 2
    assert packet.truncated is True


@pytest.mark.unit
def test_run_returns_empty_metrics_for_no_match(
    worker: RedshiftWorker, legal_ops_caller: CallerContext,
) -> None:
    packet = worker.run(
        query_type="matter_lookup",
        params={"matter_id": "no_such_matter"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 0
    assert packet.metrics == []
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_worker.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `worker.py`**

`src/lina_redshift/worker.py`:

```python
"""RedshiftWorker — the boundary that resolves a query plan into a ResultPacket."""

from __future__ import annotations

import time
from typing import Any

from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import RealDictCursor
from pydantic import ValidationError
from ulid import ULID

from lina_redshift.caller import CallerContext
from lina_redshift.errors import (
    AuthorizationError,
    InvalidParametersError,
    QueryTimeoutError,
    RedshiftConnectionError,
    UnknownTemplateError,
    WorkerError,
    WorkerInternalError,
)
from lina_redshift.logging_config import bind_call_context, get_logger
from lina_redshift.packet import ErrorPacket, ResultPacket
from lina_redshift.templates import TEMPLATE_REGISTRY, get_template


class RedshiftWorker:
    def __init__(self, *, connection: PgConnection) -> None:
        self._conn = connection
        self._log = get_logger("lina_redshift.worker")

    def run(
        self,
        *,
        query_type: str,
        params: dict[str, Any],
        caller: CallerContext,
    ) -> ResultPacket | ErrorPacket:
        sql_trace_id = str(ULID())
        log = bind_call_context(
            self._log,
            sql_trace_id=sql_trace_id,
            request_id=caller.request_id,
            user_id=caller.user_id,
            query_type=query_type,
            template_version="?",
        )
        try:
            template = get_template(query_type)
        except UnknownTemplateError as exc:
            log.warning("unknown_template", outcome=type(exc).__name__)
            return ErrorPacket.from_exception(
                exc, sql_trace_id=sql_trace_id, result_type=query_type,
            )

        log = bind_call_context(
            self._log,
            sql_trace_id=sql_trace_id,
            request_id=caller.request_id,
            user_id=caller.user_id,
            query_type=query_type,
            template_version=template.template_version,
        )

        if not caller.has_any_role(template.allowed_roles):
            exc = AuthorizationError(
                f"caller {caller.user_id!r} lacks any of {sorted(template.allowed_roles)} "
                f"required by {query_type!r}"
            )
            log.warning("authorization_failed", outcome="AuthorizationError")
            return ErrorPacket.from_exception(
                exc, sql_trace_id=sql_trace_id, result_type=query_type,
            )

        try:
            parsed = template.Params.model_validate(params)
        except ValidationError as exc:
            wrapped = InvalidParametersError(str(exc))
            log.warning("invalid_parameters", outcome="InvalidParametersError")
            return ErrorPacket.from_exception(
                wrapped, sql_trace_id=sql_trace_id, result_type=query_type,
            )

        try:
            sql, binds = template.build_sql(parsed)
        except Exception as exc:  # build_sql failures are programmer error
            log.error("build_sql_failed", outcome="WorkerInternalError", exc_info=exc)
            return ErrorPacket.from_exception(
                WorkerInternalError(str(exc)),
                sql_trace_id=sql_trace_id, result_type=query_type,
            )

        start = time.perf_counter()
        try:
            rows = self._execute(sql=sql, binds=binds)
        except WorkerError as exc:
            log.warning("query_failed", outcome=type(exc).__name__)
            return ErrorPacket.from_exception(
                exc, sql_trace_id=sql_trace_id, result_type=query_type,
            )

        duration_ms = int((time.perf_counter() - start) * 1000)
        shaped = template.shape_packet(rows)
        truncated = len(shaped) >= binds.get("limit", 0)
        log.info(
            "call_complete",
            outcome="success",
            duration_ms=duration_ms,
            row_count=len(shaped),
            truncated=truncated,
        )
        return ResultPacket(
            result_type=query_type,
            metrics=shaped,
            sql_trace_id=sql_trace_id,
            row_count=len(shaped),
            truncated=truncated,
        )

    def _execute(self, *, sql: str, binds: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, binds)
                return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            msg = str(exc).lower()
            if "statement timeout" in msg or "canceling statement due to" in msg:
                raise QueryTimeoutError(str(exc)) from exc
            if "connection" in msg or "ssl" in msg:
                raise RedshiftConnectionError(str(exc)) from exc
            raise WorkerInternalError(str(exc)) from exc


# Sanity check: importing this module ensures every template is registered.
assert TEMPLATE_REGISTRY, "no templates registered"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_worker.py -v`
Expected: 6 passed.

- [ ] **Step 5: Run full unit suite**

Run: `pytest -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/worker.py tests/unit/test_worker.py
git commit -m "feat(worker): add RedshiftWorker with auth + validation + structured logging"
```

---

## Task 23: Seed — Billing Codes

**Files:**
- Create: `src/lina_redshift/seed/__init__.py`
- Create: `src/lina_redshift/seed/billing_codes.py`
- Create: `tests/unit/test_seed_billing_codes.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_seed_billing_codes.py`:

```python
"""Unit tests for the billing-code seed module."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.seed.billing_codes import BILLING_CODES, load_billing_codes

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


@pytest.mark.unit
def test_billing_codes_constant_has_three_categories() -> None:
    types = {c.code_type for c in BILLING_CODES}
    assert types == {"task", "activity", "expense"}


@pytest.mark.unit
def test_load_billing_codes_inserts_rows(applied: PgConnection) -> None:
    load_billing_codes(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_billing_code")
        count = cur.fetchone()[0]
    assert count == len(BILLING_CODES)


@pytest.mark.unit
def test_load_billing_codes_idempotent(applied: PgConnection) -> None:
    load_billing_codes(applied)
    load_billing_codes(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_billing_code")
        assert cur.fetchone()[0] == len(BILLING_CODES)


@pytest.mark.unit
def test_billing_codes_have_unique_ids() -> None:
    ids = [c.billing_code_id for c in BILLING_CODES]
    assert len(ids) == len(set(ids))
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_seed_billing_codes.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `seed/__init__.py`**

`src/lina_redshift/seed/__init__.py`:

```python
"""Seed loaders for the legal_matter_spend schema."""

from __future__ import annotations

from psycopg2.extensions import connection as PgConnection


def load_all(connection: PgConnection, *, reset: bool = False) -> None:
    """Load all seed data layers in dependency order."""
    from lina_redshift.seed.billing_codes import load_billing_codes
    from lina_redshift.seed.named_entities import load_named_entities
    from lina_redshift.seed.generator import load_bulk_generated

    if reset:
        _truncate_all(connection)

    load_billing_codes(connection)
    load_named_entities(connection)
    load_bulk_generated(connection)
    _refresh_materialized_views(connection)


_TRUNCATE_ORDER: list[str] = [
    "fact_invoice_line_item",
    "fact_invoice",
    "fact_timekeeper_rate",
    "fact_matter_budget",
    "fact_accrual",
    "bridge_matter_vendor",
    "bridge_matter_person",
    "bridge_matter_allocation",
    "dim_timekeeper",
    "dim_matter",
    "dim_vendor",
    "dim_billing_code",
    "dim_cost_center",
    "dim_legal_entity",
]

_MATERIALIZED_VIEWS: list[str] = [
    "mv_matter_spend_summary",
    "mv_vendor_spend_summary",
    "mv_timekeeper_rate_analysis",
]


def _truncate_all(connection: PgConnection) -> None:
    with connection.cursor() as cur:
        for table in _TRUNCATE_ORDER:
            cur.execute(f"TRUNCATE {table} CASCADE")
    connection.commit()


def _refresh_materialized_views(connection: PgConnection) -> None:
    """Refresh MVs (Postgres requires explicit refresh; Redshift handles via AUTO REFRESH)."""
    with connection.cursor() as cur:
        for mv in _MATERIALIZED_VIEWS:
            cur.execute(f"REFRESH MATERIALIZED VIEW {mv}")
    connection.commit()
```

- [ ] **Step 4: Implement `seed/billing_codes.py`**

`src/lina_redshift/seed/billing_codes.py`:

```python
"""Hardcoded subset of UTBMS task/activity/expense codes."""

from __future__ import annotations

from dataclasses import dataclass

from psycopg2.extensions import connection as PgConnection


@dataclass(frozen=True)
class BillingCode:
    billing_code_id: str
    code: str
    code_type: str    # "task" | "activity" | "expense"
    code_set: str     # "UTBMS"
    description: str


_TASK_CODES: list[BillingCode] = [
    BillingCode(f"bc_task_{c}", c, "task", "UTBMS", desc)
    for c, desc in [
        ("L100", "Case Assessment, Development and Administration"),
        ("L110", "Fact Investigation/Development"),
        ("L120", "Analysis/Strategy"),
        ("L130", "Experts/Consultants"),
        ("L140", "Document/File Management"),
        ("L150", "Budgeting"),
        ("L160", "Settlement/Non-Binding ADR"),
        ("L190", "Other Case Assessment"),
        ("L200", "Pre-Trial Pleadings and Motions"),
        ("L210", "Pleadings"),
        ("L220", "Preliminary Injunctions/Provisional Remedies"),
        ("L230", "Court Mandated Conferences"),
        ("L240", "Dispositive Motions"),
        ("L250", "Other Written Motions and Submissions"),
        ("L300", "Discovery"),
        ("L310", "Written Discovery"),
        ("L320", "Document Production"),
        ("L330", "Depositions"),
        ("L340", "Expert Discovery"),
        ("L350", "Discovery Motions"),
        ("L400", "Trial Preparation and Trial"),
        ("L410", "Fact Witnesses"),
        ("L420", "Expert Witnesses"),
        ("L430", "Written Motions and Submissions"),
        ("L440", "Other Trial Preparation"),
    ]
]

_ACTIVITY_CODES: list[BillingCode] = [
    BillingCode(f"bc_activity_{c}", c, "activity", "UTBMS", desc)
    for c, desc in [
        ("A101", "Plan and prepare for"),
        ("A102", "Research"),
        ("A103", "Draft/revise"),
        ("A104", "Review/analyze"),
        ("A105", "Communicate (in firm)"),
        ("A106", "Communicate (with client)"),
        ("A107", "Communicate (other outside counsel)"),
        ("A108", "Communicate (other external)"),
        ("A109", "Appear for/attend"),
        ("A110", "Manage data/files"),
    ]
]

_EXPENSE_CODES: list[BillingCode] = [
    BillingCode(f"bc_expense_{c}", c, "expense", "UTBMS", desc)
    for c, desc in [
        ("E101", "Copying"),
        ("E102", "Outside printing"),
        ("E103", "Word processing"),
        ("E104", "Facsimile"),
        ("E105", "Telephone"),
        ("E106", "Online research"),
        ("E107", "Delivery services/messengers"),
        ("E108", "Postage"),
        ("E109", "Local travel"),
        ("E110", "Out-of-town travel"),
        ("E111", "Meals"),
        ("E112", "Court fees"),
        ("E113", "Subpoena fees"),
        ("E114", "Witness fees"),
        ("E115", "Deposition transcripts"),
    ]
]

BILLING_CODES: list[BillingCode] = [*_TASK_CODES, *_ACTIVITY_CODES, *_EXPENSE_CODES]


def load_billing_codes(connection: PgConnection) -> None:
    """Insert billing codes idempotently via UPSERT-style ON CONFLICT."""
    with connection.cursor() as cur:
        for c in BILLING_CODES:
            cur.execute(
                "INSERT INTO dim_billing_code (billing_code_id, code, code_type, "
                "code_set, description, active_status, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (billing_code_id) DO NOTHING",
                (c.billing_code_id, c.code, c.code_type, c.code_set, c.description),
            )
    connection.commit()
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_seed_billing_codes.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add src/lina_redshift/seed tests/unit/test_seed_billing_codes.py
git commit -m "feat(seed): add UTBMS billing-code reference data and idempotent loader"
```

---

## Task 24: Seed — Named Entities

**Files:**
- Create: `src/lina_redshift/seed/named_entities.py`
- Create: `tests/unit/test_seed_named_entities.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_seed_named_entities.py`:

```python
"""Unit tests for named-entity seed."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.seed.named_entities import (
    NAMED_INVOICES,
    NAMED_LINE_ITEMS,
    NAMED_MATTERS,
    NAMED_TIMEKEEPERS,
    NAMED_VENDORS,
    load_named_entities,
)

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


@pytest.mark.unit
def test_named_matters_have_recognizable_ids() -> None:
    ids = {m.matter_id for m in NAMED_MATTERS}
    assert "matter_acme_v_beta" in ids
    assert "matter_acme_privacy_review" in ids
    assert "matter_acme_employment_2023" in ids


@pytest.mark.unit
def test_named_vendors_recognizable() -> None:
    ids = {v.vendor_id for v in NAMED_VENDORS}
    assert ids >= {"vendor_walker", "vendor_jones", "vendor_meridian"}


@pytest.mark.unit
def test_load_named_entities_inserts_all(applied: PgConnection) -> None:
    load_named_entities(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        assert cur.fetchone()[0] == len(NAMED_MATTERS)
        cur.execute("SELECT count(*) FROM dim_vendor")
        assert cur.fetchone()[0] == len(NAMED_VENDORS)
        cur.execute("SELECT count(*) FROM dim_timekeeper")
        assert cur.fetchone()[0] == len(NAMED_TIMEKEEPERS)
        cur.execute("SELECT count(*) FROM fact_invoice")
        assert cur.fetchone()[0] == len(NAMED_INVOICES)
        cur.execute("SELECT count(*) FROM fact_invoice_line_item")
        assert cur.fetchone()[0] == len(NAMED_LINE_ITEMS)


@pytest.mark.unit
def test_named_ids_are_unique() -> None:
    matter_ids = [m.matter_id for m in NAMED_MATTERS]
    assert len(matter_ids) == len(set(matter_ids))
    vendor_ids = [v.vendor_id for v in NAMED_VENDORS]
    assert len(vendor_ids) == len(set(vendor_ids))
    tk_ids = [t.timekeeper_id for t in NAMED_TIMEKEEPERS]
    assert len(tk_ids) == len(set(tk_ids))


@pytest.mark.unit
def test_load_named_entities_idempotent(applied: PgConnection) -> None:
    load_named_entities(applied)
    load_named_entities(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        assert cur.fetchone()[0] == len(NAMED_MATTERS)
```

- [ ] **Step 2: Run tests to confirm failure**

Run: `pytest tests/unit/test_seed_named_entities.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `named_entities.py`**

`src/lina_redshift/seed/named_entities.py`:

```python
"""Hand-written named entities for golden-path tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from psycopg2.extensions import connection as PgConnection


@dataclass(frozen=True)
class LegalEntity:
    legal_entity_id: str
    legal_entity_name: str
    country_code: str
    entity_status: str = "active"


@dataclass(frozen=True)
class CostCenter:
    cost_center_id: str
    cost_center_name: str
    business_unit: str
    department: str
    active_status: str = "active"


@dataclass(frozen=True)
class Vendor:
    vendor_id: str
    vendor_name: str
    vendor_type: str
    vendor_status: str
    country_code: str
    default_currency_code: str
    preferred_panel_flag: bool
    source_system: str = "named_seed"


@dataclass(frozen=True)
class Matter:
    matter_id: str
    client_matter_id: str
    matter_name: str
    matter_type: str
    practice_area: str
    matter_status: str
    jurisdiction: str
    risk_level: str
    open_date: date
    close_date: date | None
    legal_entity_id: str
    business_unit: str
    matter_owner_user_id: str
    budget_amount: Decimal
    budget_currency_code: str
    source_system: str = "named_seed"


@dataclass(frozen=True)
class Timekeeper:
    timekeeper_id: str
    vendor_id: str
    timekeeper_name: str
    timekeeper_classification: str
    years_of_experience: int
    office_country_code: str
    active_status: str = "active"


@dataclass(frozen=True)
class TimekeeperRate:
    rate_id: str
    timekeeper_id: str
    vendor_id: str
    rate_type: str
    hourly_rate: Decimal
    currency_code: str
    effective_start_date: date
    effective_end_date: date | None
    approval_status: str = "approved"


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    invoice_number: str
    matter_id: str
    client_matter_id: str
    vendor_id: str
    invoice_date: date
    invoice_status: str
    currency_code: str
    invoice_total_amount: Decimal
    fee_total_amount: Decimal
    expense_total_amount: Decimal
    approved_amount: Decimal
    paid_amount: Decimal | None
    ledes_format: str = "LEDES_1998B"


@dataclass(frozen=True)
class LineItem:
    invoice_line_item_id: str
    invoice_id: str
    line_item_number: int
    matter_id: str
    client_matter_id: str
    vendor_id: str
    timekeeper_id: str | None
    line_item_date: date
    line_item_type: str
    task_code: str | None
    activity_code: str | None
    expense_code: str | None
    units: Decimal | None
    unit_rate: Decimal | None
    line_item_total_amount: Decimal
    currency_code: str
    usd_amount: Decimal
    fx_rate_to_usd: Decimal
    billing_guideline_flag: bool = False


NAMED_LEGAL_ENTITIES: list[LegalEntity] = [
    LegalEntity("le_acme_us", "Acme Corp US, Inc.", "US"),
    LegalEntity("le_acme_uk", "Acme Corp UK Ltd.", "GB"),
    LegalEntity("le_acme_de", "Acme Corp Deutschland GmbH", "DE"),
]

NAMED_COST_CENTERS: list[CostCenter] = [
    CostCenter("cc_legal_ops", "Legal Operations", "Legal", "Legal Ops"),
    CostCenter("cc_eng_platform", "Engineering Platform", "Engineering", "Platform"),
]

NAMED_VENDORS: list[Vendor] = [
    Vendor("vendor_walker", "Walker & Associates LLP", "law_firm",
           "preferred", "US", "USD", True),
    Vendor("vendor_jones", "Jones Privacy Law", "law_firm",
           "active", "US", "USD", False),
    Vendor("vendor_meridian", "Meridian Counsel UK", "law_firm",
           "active", "GB", "GBP", True),
]

NAMED_MATTERS: list[Matter] = [
    Matter("matter_acme_v_beta", "LIT-2024-001", "Acme v. Beta Litigation",
           "litigation", "Litigation", "open", "CA", "high",
           date(2024, 6, 1), None, "le_acme_us", "Enterprise",
           "user_jane_smith", Decimal("500000.00"), "USD"),
    Matter("matter_acme_privacy_review", "ADV-2024-042", "Acme Privacy Program Review",
           "advisory", "Privacy", "open", "US", "medium",
           date(2024, 9, 15), None, "le_acme_us", "Product",
           "user_alex_lee", Decimal("150000.00"), "USD"),
    Matter("matter_acme_employment_2023", "EMP-2023-007", "Smith v. Acme Employment",
           "employment", "Employment", "closed", "NY", "medium",
           date(2023, 1, 10), date(2024, 3, 30), "le_acme_us", "HR",
           "user_jane_smith", Decimal("75000.00"), "USD"),
]

NAMED_TIMEKEEPERS: list[Timekeeper] = [
    Timekeeper("tk_walker_partner", "vendor_walker", "Patricia Walker", "Partner", 22, "US"),
    Timekeeper("tk_walker_associate", "vendor_walker", "Roy Sanchez", "Associate", 5, "US"),
    Timekeeper("tk_jones_partner", "vendor_jones", "Daniel Jones", "Partner", 18, "US"),
    Timekeeper("tk_meridian_partner", "vendor_meridian", "Imogen Hart", "Partner", 25, "GB"),
    Timekeeper("tk_meridian_paralegal", "vendor_meridian", "Oliver Reed", "Paralegal", 8, "GB"),
]

NAMED_RATES: list[TimekeeperRate] = [
    TimekeeperRate("rate_walker_partner_2024", "tk_walker_partner", "vendor_walker",
                   "standard", Decimal("950"), "USD",
                   date(2024, 1, 1), date(2024, 12, 31)),
    TimekeeperRate("rate_walker_partner_2025", "tk_walker_partner", "vendor_walker",
                   "standard", Decimal("995"), "USD",
                   date(2025, 1, 1), None),
    TimekeeperRate("rate_walker_associate_2024", "tk_walker_associate", "vendor_walker",
                   "standard", Decimal("525"), "USD", date(2024, 1, 1), None),
    TimekeeperRate("rate_jones_partner_2024", "tk_jones_partner", "vendor_jones",
                   "discounted", Decimal("750"), "USD", date(2024, 1, 1), None),
    TimekeeperRate("rate_meridian_partner_2024", "tk_meridian_partner", "vendor_meridian",
                   "standard", Decimal("780"), "GBP", date(2024, 1, 1), None),
    TimekeeperRate("rate_meridian_paralegal_2024", "tk_meridian_paralegal", "vendor_meridian",
                   "standard", Decimal("220"), "GBP", date(2024, 1, 1), None),
]

NAMED_INVOICES: list[Invoice] = [
    Invoice("inv_walker_2024q3", "WALK-24-Q3-001", "matter_acme_v_beta", "LIT-2024-001",
            "vendor_walker", date(2024, 9, 30), "paid", "USD",
            Decimal("85000.00"), Decimal("82000.00"), Decimal("3000.00"),
            Decimal("80000.00"), Decimal("80000.00")),
    Invoice("inv_walker_2024q4", "WALK-24-Q4-002", "matter_acme_v_beta", "LIT-2024-001",
            "vendor_walker", date(2024, 12, 20), "approved", "USD",
            Decimal("105000.00"), Decimal("100000.00"), Decimal("5000.00"),
            Decimal("100000.00"), None),
    Invoice("inv_jones_2024q4", "JONES-24-Q4-001", "matter_acme_privacy_review",
            "ADV-2024-042", "vendor_jones", date(2024, 12, 15), "paid", "USD",
            Decimal("32000.00"), Decimal("31000.00"), Decimal("1000.00"),
            Decimal("30000.00"), Decimal("30000.00")),
    Invoice("inv_meridian_2025q1", "MER-25-Q1-001", "matter_acme_v_beta", "LIT-2024-001",
            "vendor_meridian", date(2025, 3, 31), "approved", "GBP",
            Decimal("18000.00"), Decimal("17500.00"), Decimal("500.00"),
            Decimal("17000.00"), None),
]

NAMED_LINE_ITEMS: list[LineItem] = [
    LineItem("li_walker_2024q3_1", "inv_walker_2024q3", 1, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_partner", date(2024, 8, 12), "fee",
             "L120", "A102", None, Decimal("12.0"), Decimal("950"),
             Decimal("11400.00"), "USD", Decimal("11400.00"), Decimal("1.0")),
    LineItem("li_walker_2024q3_2", "inv_walker_2024q3", 2, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_associate", date(2024, 8, 14), "fee",
             "L210", "A103", None, Decimal("40.0"), Decimal("525"),
             Decimal("21000.00"), "USD", Decimal("21000.00"), Decimal("1.0")),
    LineItem("li_walker_2024q3_3", "inv_walker_2024q3", 3, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", None, date(2024, 8, 20), "expense",
             None, None, "E110", None, None,
             Decimal("3000.00"), "USD", Decimal("3000.00"), Decimal("1.0")),
    LineItem("li_walker_2024q4_1", "inv_walker_2024q4", 1, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_partner", date(2024, 11, 5), "fee",
             "L240", "A103", None, Decimal("24.0"), Decimal("950"),
             Decimal("22800.00"), "USD", Decimal("22800.00"), Decimal("1.0"), True),
    LineItem("li_walker_2024q4_2", "inv_walker_2024q4", 2, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_associate", date(2024, 11, 8), "fee",
             "L310", "A104", None, Decimal("80.0"), Decimal("525"),
             Decimal("42000.00"), "USD", Decimal("42000.00"), Decimal("1.0")),
    LineItem("li_walker_2024q4_3", "inv_walker_2024q4", 3, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", "tk_walker_partner", date(2024, 12, 1), "fee",
             "L160", "A106", None, Decimal("36.0"), Decimal("950"),
             Decimal("34200.00"), "USD", Decimal("34200.00"), Decimal("1.0")),
    LineItem("li_walker_2024q4_4", "inv_walker_2024q4", 4, "matter_acme_v_beta", "LIT-2024-001",
             "vendor_walker", None, date(2024, 12, 10), "expense",
             None, None, "E115", None, None,
             Decimal("5000.00"), "USD", Decimal("5000.00"), Decimal("1.0")),
    LineItem("li_jones_2024q4_1", "inv_jones_2024q4", 1, "matter_acme_privacy_review",
             "ADV-2024-042", "vendor_jones", "tk_jones_partner", date(2024, 11, 18), "fee",
             "L120", "A102", None, Decimal("32.0"), Decimal("750"),
             Decimal("24000.00"), "USD", Decimal("24000.00"), Decimal("1.0")),
    LineItem("li_jones_2024q4_2", "inv_jones_2024q4", 2, "matter_acme_privacy_review",
             "ADV-2024-042", "vendor_jones", "tk_jones_partner", date(2024, 11, 25), "fee",
             "L130", "A103", None, Decimal("9.0"), Decimal("750"),
             Decimal("6750.00"), "USD", Decimal("6750.00"), Decimal("1.0")),
    LineItem("li_jones_2024q4_3", "inv_jones_2024q4", 3, "matter_acme_privacy_review",
             "ADV-2024-042", "vendor_jones", None, date(2024, 12, 1), "expense",
             None, None, "E106", None, None,
             Decimal("1250.00"), "USD", Decimal("1250.00"), Decimal("1.0")),
    LineItem("li_meridian_2025q1_1", "inv_meridian_2025q1", 1, "matter_acme_v_beta",
             "LIT-2024-001", "vendor_meridian", "tk_meridian_partner", date(2025, 2, 14), "fee",
             "L320", "A104", None, Decimal("16.0"), Decimal("780"),
             Decimal("12480.00"), "GBP", Decimal("15600.00"), Decimal("1.25")),
    LineItem("li_meridian_2025q1_2", "inv_meridian_2025q1", 2, "matter_acme_v_beta",
             "LIT-2024-001", "vendor_meridian", "tk_meridian_paralegal", date(2025, 2, 20), "fee",
             "L320", "A110", None, Decimal("23.0"), Decimal("220"),
             Decimal("5060.00"), "GBP", Decimal("6325.00"), Decimal("1.25"), True),
]


def load_named_entities(connection: PgConnection) -> None:
    """Insert all named entities idempotently."""
    with connection.cursor() as cur:
        for e in NAMED_LEGAL_ENTITIES:
            cur.execute(
                "INSERT INTO dim_legal_entity (legal_entity_id, legal_entity_name, "
                "country_code, entity_status, created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (legal_entity_id) DO NOTHING",
                (e.legal_entity_id, e.legal_entity_name, e.country_code, e.entity_status),
            )
        for cc in NAMED_COST_CENTERS:
            cur.execute(
                "INSERT INTO dim_cost_center (cost_center_id, cost_center_name, "
                "business_unit, department, active_status, created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (cost_center_id) DO NOTHING",
                (cc.cost_center_id, cc.cost_center_name, cc.business_unit,
                 cc.department, cc.active_status),
            )
        for v in NAMED_VENDORS:
            cur.execute(
                "INSERT INTO dim_vendor (vendor_id, vendor_name, vendor_type, vendor_status, "
                "country_code, default_currency_code, preferred_panel_flag, "
                "created_at, updated_at, source_system) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s) "
                "ON CONFLICT (vendor_id) DO NOTHING",
                (v.vendor_id, v.vendor_name, v.vendor_type, v.vendor_status,
                 v.country_code, v.default_currency_code, v.preferred_panel_flag,
                 v.source_system),
            )
        for m in NAMED_MATTERS:
            cur.execute(
                "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
                "matter_type, practice_area, matter_status, jurisdiction, risk_level, "
                "open_date, close_date, legal_entity_id, business_unit, "
                "matter_owner_user_id, budget_amount, budget_currency_code, "
                "created_at, updated_at, source_system) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s) "
                "ON CONFLICT (matter_id) DO NOTHING",
                (m.matter_id, m.client_matter_id, m.matter_name, m.matter_type,
                 m.practice_area, m.matter_status, m.jurisdiction, m.risk_level,
                 m.open_date, m.close_date, m.legal_entity_id, m.business_unit,
                 m.matter_owner_user_id, m.budget_amount, m.budget_currency_code,
                 m.source_system),
            )
        for t in NAMED_TIMEKEEPERS:
            cur.execute(
                "INSERT INTO dim_timekeeper (timekeeper_id, vendor_id, timekeeper_name, "
                "timekeeper_classification, years_of_experience, office_country_code, "
                "active_status, created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (timekeeper_id) DO NOTHING",
                (t.timekeeper_id, t.vendor_id, t.timekeeper_name,
                 t.timekeeper_classification, t.years_of_experience,
                 t.office_country_code, t.active_status),
            )
        for r in NAMED_RATES:
            cur.execute(
                "INSERT INTO fact_timekeeper_rate (rate_id, timekeeper_id, vendor_id, "
                "rate_type, hourly_rate, currency_code, effective_start_date, "
                "effective_end_date, approval_status, created_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP) "
                "ON CONFLICT (rate_id) DO NOTHING",
                (r.rate_id, r.timekeeper_id, r.vendor_id, r.rate_type,
                 r.hourly_rate, r.currency_code, r.effective_start_date,
                 r.effective_end_date, r.approval_status),
            )
        for inv in NAMED_INVOICES:
            cur.execute(
                "INSERT INTO fact_invoice (invoice_id, invoice_number, matter_id, "
                "client_matter_id, vendor_id, invoice_date, invoice_status, "
                "currency_code, invoice_total_amount, fee_total_amount, "
                "expense_total_amount, approved_amount, paid_amount, ledes_format, "
                "created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (invoice_id) DO NOTHING",
                (inv.invoice_id, inv.invoice_number, inv.matter_id, inv.client_matter_id,
                 inv.vendor_id, inv.invoice_date, inv.invoice_status, inv.currency_code,
                 inv.invoice_total_amount, inv.fee_total_amount, inv.expense_total_amount,
                 inv.approved_amount, inv.paid_amount, inv.ledes_format),
            )
        for li in NAMED_LINE_ITEMS:
            cur.execute(
                "INSERT INTO fact_invoice_line_item (invoice_line_item_id, invoice_id, "
                "line_item_number, matter_id, client_matter_id, vendor_id, timekeeper_id, "
                "line_item_date, line_item_type, task_code, activity_code, expense_code, "
                "units, unit_rate, line_item_total_amount, currency_code, usd_amount, "
                "fx_rate_to_usd, billing_guideline_flag, created_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP) "
                "ON CONFLICT (invoice_line_item_id) DO NOTHING",
                (li.invoice_line_item_id, li.invoice_id, li.line_item_number,
                 li.matter_id, li.client_matter_id, li.vendor_id, li.timekeeper_id,
                 li.line_item_date, li.line_item_type, li.task_code, li.activity_code,
                 li.expense_code, li.units, li.unit_rate, li.line_item_total_amount,
                 li.currency_code, li.usd_amount, li.fx_rate_to_usd,
                 li.billing_guideline_flag),
            )
    connection.commit()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_seed_named_entities.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/seed/named_entities.py tests/unit/test_seed_named_entities.py
git commit -m "feat(seed): add hand-written named entities for golden-path tests"
```

---

## Task 25: Seed — Bulk Generator

**Files:**
- Create: `src/lina_redshift/seed/generator.py`
- Create: `tests/unit/test_seed_generator.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_seed_generator.py`:

```python
"""Unit tests for the deterministic Faker bulk generator."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.seed.generator import (
    GeneratedSeed,
    generate_seed,
    load_bulk_generated,
)
from lina_redshift.seed.named_entities import load_named_entities

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    load_named_entities(pg_conn)
    return pg_conn


@pytest.mark.unit
def test_generator_is_deterministic() -> None:
    a = generate_seed()
    b = generate_seed()
    assert [m.matter_id for m in a.matters] == [m.matter_id for m in b.matters]
    assert [li.invoice_line_item_id for li in a.line_items] == [
        li.invoice_line_item_id for li in b.line_items
    ]


@pytest.mark.unit
def test_generator_volumes_match_spec() -> None:
    seed = generate_seed()
    assert len(seed.matters) == 100
    assert len(seed.vendors) == 25
    assert len(seed.timekeepers) == 200
    assert len(seed.invoices) == 600
    assert 5_500 <= len(seed.line_items) <= 6_500


@pytest.mark.unit
def test_generated_ids_disjoint_from_named() -> None:
    """Generated IDs must not collide with hand-written named entity IDs."""
    seed = generate_seed()
    matter_ids = {m.matter_id for m in seed.matters}
    assert "matter_acme_v_beta" not in matter_ids
    vendor_ids = {v.vendor_id for v in seed.vendors}
    assert "vendor_walker" not in vendor_ids


@pytest.mark.unit
def test_generated_currency_distribution() -> None:
    """80% USD, 10% GBP, 5% EUR, 5% other."""
    seed = generate_seed()
    currencies = [inv.currency_code for inv in seed.invoices]
    usd = sum(1 for c in currencies if c == "USD")
    assert 0.70 < usd / len(currencies) < 0.90


@pytest.mark.unit
def test_generated_line_items_some_billing_flagged() -> None:
    seed = generate_seed()
    flagged = sum(1 for li in seed.line_items if li.billing_guideline_flag)
    assert flagged > 0


@pytest.mark.unit
def test_load_bulk_generated_inserts_rows(applied: PgConnection) -> None:
    load_bulk_generated(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        assert cur.fetchone()[0] >= 100  # named + generated
        cur.execute("SELECT count(*) FROM fact_invoice")
        assert cur.fetchone()[0] >= 600
        cur.execute("SELECT count(*) FROM fact_invoice_line_item")
        assert cur.fetchone()[0] >= 5_500
```

- [ ] **Step 2: Run test to confirm failure**

Run: `pytest tests/unit/test_seed_generator.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `seed/generator.py`**

`src/lina_redshift/seed/generator.py`:

```python
"""Deterministic Faker-driven bulk seed generator (fixed seed = 42)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from psycopg2.extensions import connection as PgConnection

from lina_redshift.seed.named_entities import (
    Invoice,
    LineItem,
    Matter,
    Timekeeper,
    TimekeeperRate,
    Vendor,
)

_SEED = 42
_PRACTICE_AREAS = (
    "Litigation", "Privacy", "Employment", "M&A",
    "IP", "Regulatory", "Real Estate", "Tax",
)
_MATTER_TYPES = ("litigation", "advisory", "transactional", "regulatory", "employment")
_MATTER_STATUSES = ("open", "open", "open", "open", "closed", "on_hold")  # weighted
_VENDOR_TYPES = ("law_firm", "law_firm", "law_firm", "consultant", "expert", "ediscovery")
_CLASSIFICATIONS_WEIGHTED = (
    *(["Partner"] * 30),
    *(["Associate"] * 50),
    *(["Paralegal"] * 15),
    *(["Counsel"] * 5),
)
_CURRENCY_WEIGHTS = (
    *(["USD"] * 80), *(["GBP"] * 10), *(["EUR"] * 5),
    *(["CAD"] * 2), *(["AUD"] * 2), *(["JPY"] * 1),
)
_FX_TO_USD = {
    "USD": Decimal("1.0"),
    "GBP": Decimal("1.25"),
    "EUR": Decimal("1.08"),
    "CAD": Decimal("0.74"),
    "AUD": Decimal("0.66"),
    "JPY": Decimal("0.0067"),
}
_TASK_CODES = ("L100", "L120", "L210", "L240", "L310", "L320", "L330", "L410")
_ACTIVITY_CODES = ("A101", "A102", "A103", "A104", "A106", "A109")
_EXPENSE_CODES = ("E101", "E106", "E110", "E111", "E115")


@dataclass
class GeneratedSeed:
    matters: list[Matter] = field(default_factory=list)
    vendors: list[Vendor] = field(default_factory=list)
    timekeepers: list[Timekeeper] = field(default_factory=list)
    rates: list[TimekeeperRate] = field(default_factory=list)
    invoices: list[Invoice] = field(default_factory=list)
    line_items: list[LineItem] = field(default_factory=list)


def generate_seed() -> GeneratedSeed:
    fake = Faker("en_US")
    Faker.seed(_SEED)
    rng = random.Random(_SEED)

    seed = GeneratedSeed()

    for i in range(25):
        seed.vendors.append(Vendor(
            vendor_id=f"vendor_gen_{i:03d}",
            vendor_name=f"{fake.last_name()} & {fake.last_name()} {rng.choice(['LLP', 'PLLC', 'PC'])}",
            vendor_type=rng.choice(_VENDOR_TYPES),
            vendor_status=rng.choice(("active", "active", "active", "preferred", "inactive")),
            country_code=rng.choice(("US", "US", "US", "GB", "DE", "CA")),
            default_currency_code=rng.choice(("USD", "USD", "USD", "GBP", "EUR")),
            preferred_panel_flag=rng.random() < 0.4,
            source_system="generator_seed",
        ))

    for j in range(200):
        v = rng.choice(seed.vendors)
        seed.timekeepers.append(Timekeeper(
            timekeeper_id=f"tk_gen_{j:04d}",
            vendor_id=v.vendor_id,
            timekeeper_name=fake.name(),
            timekeeper_classification=rng.choice(_CLASSIFICATIONS_WEIGHTED),
            years_of_experience=rng.randint(1, 35),
            office_country_code=v.country_code,
        ))
        rate_value = {
            "Partner": rng.randint(700, 1200),
            "Associate": rng.randint(350, 650),
            "Paralegal": rng.randint(150, 280),
            "Counsel": rng.randint(550, 850),
        }[seed.timekeepers[-1].timekeeper_classification]
        seed.rates.append(TimekeeperRate(
            rate_id=f"rate_gen_{j:04d}",
            timekeeper_id=seed.timekeepers[-1].timekeeper_id,
            vendor_id=v.vendor_id,
            rate_type="standard",
            hourly_rate=Decimal(str(rate_value)),
            currency_code=v.default_currency_code,
            effective_start_date=date(2023, 1, 1),
            effective_end_date=None,
        ))

    for k in range(100):
        open_date = _random_date(rng, date(2023, 1, 1), date(2025, 3, 31))
        status = rng.choice(_MATTER_STATUSES)
        close_date = (
            _random_date(rng, open_date, date(2025, 6, 30))
            if status == "closed"
            else None
        )
        seed.matters.append(Matter(
            matter_id=f"matter_gen_{k:03d}",
            client_matter_id=f"GEN-{2023 + k % 3}-{k:04d}",
            matter_name=f"{fake.company()} {rng.choice(['Litigation', 'Review', 'Investigation', 'Advisory'])}",
            matter_type=rng.choice(_MATTER_TYPES),
            practice_area=rng.choice(_PRACTICE_AREAS),
            matter_status=status,
            jurisdiction=rng.choice(("CA", "NY", "TX", "DE", "US", "GB")),
            risk_level=rng.choice(("low", "medium", "medium", "high")),
            open_date=open_date,
            close_date=close_date,
            legal_entity_id=rng.choice(("le_acme_us", "le_acme_uk", "le_acme_de")),
            business_unit=rng.choice(("Enterprise", "Product", "HR", "Finance")),
            matter_owner_user_id=f"user_gen_{rng.randint(0, 49):03d}",
            budget_amount=Decimal(str(rng.randint(50_000, 1_500_000))),
            budget_currency_code="USD",
            source_system="generator_seed",
        ))

    invoice_idx = 0
    line_item_idx = 0
    for n in range(600):
        matter = rng.choice(seed.matters)
        possible_vendors = [
            t for t in seed.timekeepers if t.vendor_id in {v.vendor_id for v in seed.vendors}
        ]
        vendor_id = rng.choice(possible_vendors).vendor_id
        invoice_date = _random_date(rng, date(2023, 1, 1), date(2025, 6, 30))
        currency = rng.choice(_CURRENCY_WEIGHTS)

        per_invoice_lines = rng.randint(8, 12)
        line_items_for_invoice: list[LineItem] = []
        running_fee = Decimal("0")
        running_expense = Decimal("0")
        for line_no in range(1, per_invoice_lines + 1):
            is_fee = rng.random() < 0.85
            tk_choices = [t for t in seed.timekeepers if t.vendor_id == vendor_id]
            tk = rng.choice(tk_choices) if tk_choices else None
            if is_fee and tk is not None:
                hours = Decimal(str(round(rng.uniform(0.5, 8.0), 1)))
                rate = next(
                    (r.hourly_rate for r in seed.rates if r.timekeeper_id == tk.timekeeper_id),
                    Decimal("500"),
                )
                amount = (hours * rate).quantize(Decimal("0.01"))
                running_fee += amount
                line_items_for_invoice.append(LineItem(
                    invoice_line_item_id=f"li_gen_{line_item_idx:06d}",
                    invoice_id=f"inv_gen_{invoice_idx:05d}",
                    line_item_number=line_no,
                    matter_id=matter.matter_id,
                    client_matter_id=matter.client_matter_id,
                    vendor_id=vendor_id,
                    timekeeper_id=tk.timekeeper_id,
                    line_item_date=invoice_date - timedelta(days=rng.randint(0, 60)),
                    line_item_type="fee",
                    task_code=rng.choice(_TASK_CODES),
                    activity_code=rng.choice(_ACTIVITY_CODES),
                    expense_code=None,
                    units=hours,
                    unit_rate=rate,
                    line_item_total_amount=amount,
                    currency_code=currency,
                    usd_amount=(amount * _FX_TO_USD[currency]).quantize(Decimal("0.01")),
                    fx_rate_to_usd=_FX_TO_USD[currency],
                    billing_guideline_flag=rng.random() < 0.05,
                ))
            else:
                amount = Decimal(str(round(rng.uniform(50, 2500), 2)))
                running_expense += amount
                line_items_for_invoice.append(LineItem(
                    invoice_line_item_id=f"li_gen_{line_item_idx:06d}",
                    invoice_id=f"inv_gen_{invoice_idx:05d}",
                    line_item_number=line_no,
                    matter_id=matter.matter_id,
                    client_matter_id=matter.client_matter_id,
                    vendor_id=vendor_id,
                    timekeeper_id=None,
                    line_item_date=invoice_date - timedelta(days=rng.randint(0, 30)),
                    line_item_type="expense",
                    task_code=None,
                    activity_code=None,
                    expense_code=rng.choice(_EXPENSE_CODES),
                    units=None,
                    unit_rate=None,
                    line_item_total_amount=amount,
                    currency_code=currency,
                    usd_amount=(amount * _FX_TO_USD[currency]).quantize(Decimal("0.01")),
                    fx_rate_to_usd=_FX_TO_USD[currency],
                ))
            line_item_idx += 1

        invoice_total = running_fee + running_expense
        seed.invoices.append(Invoice(
            invoice_id=f"inv_gen_{invoice_idx:05d}",
            invoice_number=f"GEN-{invoice_idx:06d}",
            matter_id=matter.matter_id,
            client_matter_id=matter.client_matter_id,
            vendor_id=vendor_id,
            invoice_date=invoice_date,
            invoice_status=rng.choice(("paid", "approved", "under_review", "received")),
            currency_code=currency,
            invoice_total_amount=invoice_total.quantize(Decimal("0.01")),
            fee_total_amount=running_fee.quantize(Decimal("0.01")),
            expense_total_amount=running_expense.quantize(Decimal("0.01")),
            approved_amount=invoice_total.quantize(Decimal("0.01")),
            paid_amount=invoice_total.quantize(Decimal("0.01")) if rng.random() < 0.7 else None,
        ))
        seed.line_items.extend(line_items_for_invoice)
        invoice_idx += 1

    return seed


def _random_date(rng: random.Random, start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, delta))


def load_bulk_generated(connection: PgConnection) -> None:
    """Generate the bulk seed and insert. Idempotent via ON CONFLICT."""
    from lina_redshift.seed.named_entities import load_named_entities  # for type symbol re-use

    seed = generate_seed()
    with connection.cursor() as cur:
        for v in seed.vendors:
            cur.execute(
                "INSERT INTO dim_vendor (vendor_id, vendor_name, vendor_type, "
                "vendor_status, country_code, default_currency_code, "
                "preferred_panel_flag, created_at, updated_at, source_system) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP, %s) ON CONFLICT (vendor_id) DO NOTHING",
                (v.vendor_id, v.vendor_name, v.vendor_type, v.vendor_status,
                 v.country_code, v.default_currency_code, v.preferred_panel_flag,
                 v.source_system),
            )
        for t in seed.timekeepers:
            cur.execute(
                "INSERT INTO dim_timekeeper (timekeeper_id, vendor_id, timekeeper_name, "
                "timekeeper_classification, years_of_experience, office_country_code, "
                "active_status, created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (timekeeper_id) DO NOTHING",
                (t.timekeeper_id, t.vendor_id, t.timekeeper_name,
                 t.timekeeper_classification, t.years_of_experience,
                 t.office_country_code, t.active_status),
            )
        for r in seed.rates:
            cur.execute(
                "INSERT INTO fact_timekeeper_rate (rate_id, timekeeper_id, vendor_id, "
                "rate_type, hourly_rate, currency_code, effective_start_date, "
                "effective_end_date, approval_status, created_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP) "
                "ON CONFLICT (rate_id) DO NOTHING",
                (r.rate_id, r.timekeeper_id, r.vendor_id, r.rate_type,
                 r.hourly_rate, r.currency_code, r.effective_start_date,
                 r.effective_end_date, r.approval_status),
            )
        for m in seed.matters:
            cur.execute(
                "INSERT INTO dim_matter (matter_id, client_matter_id, matter_name, "
                "matter_type, practice_area, matter_status, jurisdiction, risk_level, "
                "open_date, close_date, legal_entity_id, business_unit, "
                "matter_owner_user_id, budget_amount, budget_currency_code, "
                "created_at, updated_at, source_system) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s) "
                "ON CONFLICT (matter_id) DO NOTHING",
                (m.matter_id, m.client_matter_id, m.matter_name, m.matter_type,
                 m.practice_area, m.matter_status, m.jurisdiction, m.risk_level,
                 m.open_date, m.close_date, m.legal_entity_id, m.business_unit,
                 m.matter_owner_user_id, m.budget_amount, m.budget_currency_code,
                 m.source_system),
            )
        for inv in seed.invoices:
            cur.execute(
                "INSERT INTO fact_invoice (invoice_id, invoice_number, matter_id, "
                "client_matter_id, vendor_id, invoice_date, invoice_status, "
                "currency_code, invoice_total_amount, fee_total_amount, "
                "expense_total_amount, approved_amount, paid_amount, ledes_format, "
                "created_at, updated_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
                "ON CONFLICT (invoice_id) DO NOTHING",
                (inv.invoice_id, inv.invoice_number, inv.matter_id, inv.client_matter_id,
                 inv.vendor_id, inv.invoice_date, inv.invoice_status, inv.currency_code,
                 inv.invoice_total_amount, inv.fee_total_amount, inv.expense_total_amount,
                 inv.approved_amount, inv.paid_amount, inv.ledes_format),
            )
        for li in seed.line_items:
            cur.execute(
                "INSERT INTO fact_invoice_line_item (invoice_line_item_id, invoice_id, "
                "line_item_number, matter_id, client_matter_id, vendor_id, timekeeper_id, "
                "line_item_date, line_item_type, task_code, activity_code, expense_code, "
                "units, unit_rate, line_item_total_amount, currency_code, usd_amount, "
                "fx_rate_to_usd, billing_guideline_flag, created_at) VALUES "
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "CURRENT_TIMESTAMP) "
                "ON CONFLICT (invoice_line_item_id) DO NOTHING",
                (li.invoice_line_item_id, li.invoice_id, li.line_item_number,
                 li.matter_id, li.client_matter_id, li.vendor_id, li.timekeeper_id,
                 li.line_item_date, li.line_item_type, li.task_code, li.activity_code,
                 li.expense_code, li.units, li.unit_rate, li.line_item_total_amount,
                 li.currency_code, li.usd_amount, li.fx_rate_to_usd,
                 li.billing_guideline_flag),
            )
    connection.commit()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_seed_generator.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/seed/generator.py tests/unit/test_seed_generator.py
git commit -m "feat(seed): add deterministic Faker bulk generator"
```

---

## Task 26: Seed — `load_all` Integration Test + MV Refresh

**Files:**
- Create: `tests/unit/test_seed_load_all.py`

- [ ] **Step 1: Write integration test**

`tests/unit/test_seed_load_all.py`:

```python
"""Verify load_all populates everything and refreshes MVs."""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner
from lina_redshift.seed import load_all

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.fixture
def applied(pg_conn: PgConnection) -> PgConnection:
    MigrationRunner(connection=pg_conn, sql_dir=SQL_DIR, target="postgres").apply_pending()
    return pg_conn


@pytest.mark.unit
def test_load_all_populates_everything(applied: PgConnection) -> None:
    load_all(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_billing_code")
        assert cur.fetchone()[0] >= 50  # ~50 utbms codes
        cur.execute("SELECT count(*) FROM dim_matter")
        assert cur.fetchone()[0] >= 100
        cur.execute("SELECT count(*) FROM fact_invoice_line_item")
        assert cur.fetchone()[0] >= 5_500


@pytest.mark.unit
def test_load_all_refreshes_materialized_views(applied: PgConnection) -> None:
    load_all(applied)

    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM mv_matter_spend_summary")
        msc = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM mv_vendor_spend_summary")
        vsc = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM mv_timekeeper_rate_analysis")
        tra = cur.fetchone()[0]
    assert msc > 0
    assert vsc > 0
    assert tra > 0


@pytest.mark.unit
def test_load_all_with_reset_truncates_first(applied: PgConnection) -> None:
    load_all(applied)
    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        first_count = cur.fetchone()[0]

    load_all(applied, reset=True)
    with applied.cursor() as cur:
        cur.execute("SELECT count(*) FROM dim_matter")
        second_count = cur.fetchone()[0]

    assert first_count == second_count  # deterministic seed → same count after reset
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_seed_load_all.py -v`
Expected: 3 passed.

- [ ] **Step 3: Run full unit suite to confirm everything still green**

Run: `pytest -v`
Expected: all tests pass; total runtime under 60 seconds.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_seed_load_all.py
git commit -m "test(seed): add load_all integration test with MV refresh check"
```

---

## Task 27: CLI — `migrate` Commands

**Files:**
- Create: `src/lina_redshift/cli.py`
- Create: `tests/unit/test_cli_migrate.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_migrate.py`:

```python
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
```

- [ ] **Step 2: Run test to confirm failure**

Run: `pytest tests/unit/test_cli_migrate.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `cli.py`**

`src/lina_redshift/cli.py`:

```python
"""`lina-redshift` CLI entry point — Click-based, JSON stdout, structured stderr."""

from __future__ import annotations

import json
import sys
from importlib import resources
from pathlib import Path
from typing import Any

import click
import psycopg2

from lina_redshift.connection import resolve_config
from lina_redshift.logging_config import configure_logging
from lina_redshift.migrations.runner import MigrationRunner, list_pending


def _migrations_sql_dir() -> Path:
    return Path(str(resources.files("lina_redshift.migrations").joinpath("sql")))


@click.group()
@click.option("--target", type=click.Choice(["postgres", "redshift"]), default="redshift")
@click.pass_context
def main(ctx: click.Context, target: str) -> None:
    configure_logging()
    ctx.ensure_object(dict)
    cfg = resolve_config(target=target)  # type: ignore[arg-type]
    ctx.obj["config"] = cfg


@main.group()
def migrate() -> None:
    """DDL migration commands."""


@migrate.command("up")
@click.pass_context
def migrate_up(ctx: click.Context) -> None:
    cfg = ctx.obj["config"]
    conn = psycopg2.connect(cfg.dsn)
    try:
        runner = MigrationRunner(connection=conn, sql_dir=_migrations_sql_dir(), target=cfg.target)
        applied = runner.apply_pending()
    finally:
        conn.close()
    click.echo(json.dumps({"applied": len(applied), "versions": applied}, indent=2))


@migrate.command("status")
@click.pass_context
def migrate_status(ctx: click.Context) -> None:
    cfg = ctx.obj["config"]
    conn = psycopg2.connect(cfg.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version varchar PRIMARY KEY, applied_at timestamp NOT NULL "
                "DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.commit()
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            applied = [r[0] for r in cur.fetchall()]
        pending = list_pending(connection=conn, sql_dir=_migrations_sql_dir())
    finally:
        conn.close()
    click.echo(json.dumps({"applied": applied, "pending": pending}, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_cli_migrate.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/cli.py tests/unit/test_cli_migrate.py
git commit -m "feat(cli): add lina-redshift migrate up and status commands"
```

---

## Task 28: CLI — `seed` Command

**Files:**
- Create: `tests/unit/test_cli_seed.py`
- Modify: `src/lina_redshift/cli.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_seed.py`:

```python
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
```

- [ ] **Step 2: Add the `seed` command to `cli.py`**

Append to `src/lina_redshift/cli.py`:

```python
@main.command("seed")
@click.option("--reset", is_flag=True, default=False)
@click.option("--named-only", "named_only", is_flag=True, default=False)
@click.option("--bulk-only", "bulk_only", is_flag=True, default=False)
@click.pass_context
def seed_cmd(ctx: click.Context, reset: bool, named_only: bool, bulk_only: bool) -> None:
    if named_only and bulk_only:
        raise click.UsageError("--named-only and --bulk-only are mutually exclusive")

    cfg = ctx.obj["config"]
    conn = psycopg2.connect(cfg.dsn)
    try:
        if named_only:
            from lina_redshift.seed.named_entities import load_named_entities
            from lina_redshift.seed.billing_codes import load_billing_codes

            if reset:
                _truncate_for_named(conn)
            load_billing_codes(conn)
            load_named_entities(conn)
        elif bulk_only:
            from lina_redshift.seed.generator import load_bulk_generated

            load_bulk_generated(conn)
        else:
            from lina_redshift.seed import load_all

            load_all(conn, reset=reset)
    finally:
        conn.close()
    click.echo(json.dumps({"loaded": True, "reset": reset}, indent=2))


def _truncate_for_named(conn: Any) -> None:
    """Light truncation for --named-only --reset."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE fact_invoice_line_item, fact_invoice, dim_matter, "
                    "dim_vendor, dim_timekeeper, dim_billing_code, dim_legal_entity, "
                    "dim_cost_center, fact_timekeeper_rate CASCADE")
    conn.commit()
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_cli_seed.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add src/lina_redshift/cli.py tests/unit/test_cli_seed.py
git commit -m "feat(cli): add seed command with --reset, --named-only, --bulk-only"
```

---

## Task 29: CLI — `run`, `explain`, `list-templates`

**Files:**
- Create: `tests/unit/test_cli_run.py`
- Modify: `src/lina_redshift/cli.py`

- [ ] **Step 1: Write failing tests**

`tests/unit/test_cli_run.py`:

```python
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
        "matter_lookup", "matter_spend_summary", "vendor_spend_summary",
        "timekeeper_rate_analysis", "invoice_search", "line_item_detail",
    }


@pytest.mark.unit
def test_run_matter_lookup(pg_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    _bootstrap(pg_dsn, monkeypatch)
    runner = CliRunner()

    result = runner.invoke(main, [
        "--target", "postgres", "run", "matter_lookup",
        "--params", '{"matter_id": "matter_acme_v_beta"}',
        "--user-id", "user_jane", "--caller-roles", "legal_ops",
    ])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["row_count"] == 1
    assert payload["metrics"][0]["matter_name"] == "Acme v. Beta Litigation"


@pytest.mark.unit
def test_run_returns_error_packet_for_unauthorized(
    pg_dsn: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap(pg_dsn, monkeypatch)
    runner = CliRunner()

    result = runner.invoke(main, [
        "--target", "postgres", "run", "matter_spend_summary",
        "--params", "{}",
        "--user-id", "user_x", "--caller-roles", "random",
    ])

    assert result.exit_code == 0  # CLI returns 0 even for error packets; payload conveys
    payload = json.loads(result.output)
    assert payload["error"]["type"] == "AuthorizationError"


@pytest.mark.unit
def test_explain_renders_sql_without_executing(
    pg_dsn: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap(pg_dsn, monkeypatch)
    runner = CliRunner()

    result = runner.invoke(main, [
        "--target", "postgres", "explain", "matter_lookup",
        "--params", '{"matter_id": "matter_acme_v_beta"}',
    ])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "vw_matter_current" in payload["sql"]
    assert "explain_plan" in payload
```

- [ ] **Step 2: Add commands to `cli.py`**

Append to `src/lina_redshift/cli.py`:

```python
@main.command("list-templates")
def list_templates_cmd() -> None:
    from lina_redshift.templates import all_templates

    payload = [
        {
            "query_type": t.query_type,
            "allowed_roles": sorted(t.allowed_roles),
            "default_limit": t.default_limit,
            "max_limit": t.max_limit,
            "template_version": t.template_version,
            "params_schema": t.Params.model_json_schema(),
        }
        for t in all_templates()
    ]
    click.echo(json.dumps(payload, indent=2, default=str))


@main.command("run")
@click.argument("query_type")
@click.option("--params", required=True)
@click.option("--user-id", required=True)
@click.option("--caller-roles", required=True, help="Comma-separated roles")
@click.option("--request-id", default="cli_request")
@click.pass_context
def run_cmd(
    ctx: click.Context,
    query_type: str,
    params: str,
    user_id: str,
    caller_roles: str,
    request_id: str,
) -> None:
    from lina_redshift.caller import CallerContext
    from lina_redshift.worker import RedshiftWorker

    cfg = ctx.obj["config"]
    parsed_params = json.loads(params)
    caller = CallerContext(
        user_id=user_id,
        roles=frozenset(r.strip() for r in caller_roles.split(",") if r.strip()),
        request_id=request_id,
    )
    conn = psycopg2.connect(cfg.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (cfg.statement_timeout_ms,))
        worker = RedshiftWorker(connection=conn)
        packet = worker.run(query_type=query_type, params=parsed_params, caller=caller)
    finally:
        conn.close()
    click.echo(packet.model_dump_json(by_alias=True, indent=2))


@main.command("explain")
@click.argument("query_type")
@click.option("--params", required=True)
@click.pass_context
def explain_cmd(ctx: click.Context, query_type: str, params: str) -> None:
    from lina_redshift.templates import get_template

    cfg = ctx.obj["config"]
    template = get_template(query_type)
    parsed_params = json.loads(params)
    parsed = template.Params.model_validate(parsed_params)
    sql, binds = template.build_sql(parsed)

    conn = psycopg2.connect(cfg.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN {sql}", binds)
            plan_lines = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    click.echo(json.dumps(
        {"sql": sql, "binds": {k: str(v) for k, v in binds.items()}, "explain_plan": plan_lines},
        indent=2, default=str,
    ))
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_cli_run.py -v`
Expected: 4 passed.

- [ ] **Step 4: Run full unit suite**

Run: `pytest -v`
Expected: all green; total ~50–60 seconds.

- [ ] **Step 5: Commit**

```bash
git add src/lina_redshift/cli.py tests/unit/test_cli_run.py
git commit -m "feat(cli): add run, explain, and list-templates commands"
```

---

## Task 30: Integration Test — Redshift Smoke

**Files:**
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_redshift_smoke.py`

These tests run only when `LINA_REDSHIFT_DSN` is set; otherwise skipped (the top-level conftest already filters them).

- [ ] **Step 1: Add integration conftest with Redshift connection fixture**

`tests/integration/conftest.py`:

```python
"""Fixtures specific to the integration suite (real Redshift Serverless)."""

from __future__ import annotations

import os
from typing import Iterator

import psycopg2
import pytest
from psycopg2.extensions import connection as PgConnection


@pytest.fixture(scope="session")
def redshift_dsn() -> str:
    dsn = os.environ.get("LINA_REDSHIFT_DSN")
    if not dsn:
        pytest.skip("LINA_REDSHIFT_DSN not set")
    return dsn


@pytest.fixture(scope="session")
def redshift_conn(redshift_dsn: str) -> Iterator[PgConnection]:
    conn = psycopg2.connect(redshift_dsn)
    conn.autocommit = True
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 2: Write integration smoke tests**

`tests/integration/test_redshift_smoke.py`:

```python
"""Smoke tests for the worker against a live Redshift Serverless workgroup.

Requires:
- LINA_REDSHIFT_DSN to be exported.
- Migrations and seed already applied to the workgroup
  (run `lina-redshift --target redshift migrate up && lina-redshift --target redshift seed`).
"""

from __future__ import annotations

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.caller import CallerContext
from lina_redshift.packet import ResultPacket
from lina_redshift.worker import RedshiftWorker


@pytest.fixture
def legal_ops_caller() -> CallerContext:
    return CallerContext(
        user_id="user_jane_smith",
        roles=frozenset({"legal_ops"}),
        request_id="integration_req",
    )


@pytest.mark.integration
def test_matter_lookup_against_redshift(
    redshift_conn: PgConnection, legal_ops_caller: CallerContext,
) -> None:
    worker = RedshiftWorker(connection=redshift_conn)
    packet = worker.run(
        query_type="matter_lookup",
        params={"matter_id": "matter_acme_v_beta"},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count == 1
    assert packet.metrics[0]["matter_name"] == "Acme v. Beta Litigation"


@pytest.mark.integration
def test_matter_spend_summary_against_redshift(
    redshift_conn: PgConnection, legal_ops_caller: CallerContext,
) -> None:
    worker = RedshiftWorker(connection=redshift_conn)
    packet = worker.run(
        query_type="matter_spend_summary",
        params={"matter_ids": ["matter_acme_v_beta"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    assert packet.row_count > 0


@pytest.mark.integration
def test_vendor_spend_summary_against_redshift(
    redshift_conn: PgConnection, legal_ops_caller: CallerContext,
) -> None:
    worker = RedshiftWorker(connection=redshift_conn)
    packet = worker.run(
        query_type="vendor_spend_summary",
        params={"vendor_ids": ["vendor_walker"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)


@pytest.mark.integration
def test_invoice_search_returns_named_invoice(
    redshift_conn: PgConnection, legal_ops_caller: CallerContext,
) -> None:
    worker = RedshiftWorker(connection=redshift_conn)
    packet = worker.run(
        query_type="invoice_search",
        params={"matter_ids": ["matter_acme_v_beta"]},
        caller=legal_ops_caller,
    )
    assert isinstance(packet, ResultPacket)
    invoice_ids = {r["invoice_id"] for r in packet.metrics}
    assert "inv_walker_2024q3" in invoice_ids
```

- [ ] **Step 3: Run integration tests**

Run: `LINA_REDSHIFT_DSN=postgresql://user:pass@workgroup-host:5439/dev pytest -m integration -v`
Expected: 4 passed (when run against a workgroup that has migrations + seed applied; otherwise skipped).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/conftest.py tests/integration/test_redshift_smoke.py
git commit -m "test(integration): add Redshift smoke tests for the four primary templates"
```

---

## Task 31: Integration Test — Redshift Dialect Parity

**Files:**
- Create: `tests/integration/test_redshift_dialect_parity.py`

- [ ] **Step 1: Write parity tests**

`tests/integration/test_redshift_dialect_parity.py`:

```python
"""Verify each migration applies cleanly to real Redshift Serverless.

These tests assume a fresh namespace; they do not clean up after themselves.
Run against a workgroup dedicated to test/CI use.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from psycopg2.extensions import connection as PgConnection

from lina_redshift.migrations.runner import MigrationRunner

SQL_DIR = Path(__file__).resolve().parents[2] / "src" / "lina_redshift" / "migrations" / "sql"


@pytest.mark.integration
def test_apply_pending_against_redshift(redshift_conn: PgConnection) -> None:
    runner = MigrationRunner(connection=redshift_conn, sql_dir=SQL_DIR, target="redshift")
    runner.apply_pending()  # idempotent; safe to re-run


@pytest.mark.integration
def test_all_18_migrations_recorded_after_apply(redshift_conn: PgConnection) -> None:
    runner = MigrationRunner(connection=redshift_conn, sql_dir=SQL_DIR, target="redshift")
    runner.apply_pending()

    with redshift_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM schema_migrations")
        assert cur.fetchone()[0] == 18


@pytest.mark.integration
def test_each_table_exists_in_redshift(redshift_conn: PgConnection) -> None:
    expected = [
        "dim_legal_entity", "dim_cost_center", "dim_billing_code",
        "dim_vendor", "dim_matter", "dim_timekeeper",
        "fact_timekeeper_rate", "fact_invoice", "fact_invoice_line_item",
        "fact_matter_budget", "fact_accrual",
        "bridge_matter_vendor", "bridge_matter_person", "bridge_matter_allocation",
    ]
    with redshift_conn.cursor() as cur:
        for table in expected:
            cur.execute(
                "SELECT count(*) FROM pg_table_def WHERE tablename = %s", (table,)
            )
            assert cur.fetchone()[0] > 0, f"table {table} not present in Redshift"


@pytest.mark.integration
def test_views_and_mvs_exist_in_redshift(redshift_conn: PgConnection) -> None:
    with redshift_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM information_schema.views WHERE table_name = 'vw_matter_current'"
        )
        assert cur.fetchone()[0] == 1
        for mv in [
            "mv_matter_spend_summary",
            "mv_vendor_spend_summary",
            "mv_timekeeper_rate_analysis",
        ]:
            cur.execute(
                "SELECT count(*) FROM stv_mv_info WHERE name = %s", (mv,)
            )
            assert cur.fetchone()[0] == 1, f"materialized view {mv} not present"
```

- [ ] **Step 2: Run integration tests**

Run: `LINA_REDSHIFT_DSN=... pytest -m integration tests/integration/test_redshift_dialect_parity.py -v`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_redshift_dialect_parity.py
git commit -m "test(integration): add dialect parity checks against real Redshift"
```

---

## Task 32: README and Quickstart

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# LINA — Redshift Matter & Spend Worker (Subsystem C)

Read-only Python worker that exposes a typed catalog of query templates over the
`legal_matter_spend` schema in Amazon Redshift. First of four subsystems described
in [`lina.md`](./lina.md). Design contract: [`docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md`](./docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md).

## Quickstart

### 1. Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Local development against Postgres

You need Docker installed. The unit suite spins up an ephemeral Postgres
automatically via `pytest-postgresql`.

```bash
pytest -v
```

Expected: ~50–60 seconds, all unit tests pass.

### 3. Try the CLI

```bash
# Spin up a Postgres yourself (Docker) and export the DSN
docker run -d --name lina-pg -e POSTGRES_PASSWORD=lina -p 5432:5432 postgres:16
export LINA_POSTGRES_DSN=postgresql://postgres:lina@localhost:5432/postgres

lina-redshift --target postgres migrate up
lina-redshift --target postgres seed
lina-redshift --target postgres list-templates
lina-redshift --target postgres run matter_lookup \
    --params '{"matter_id": "matter_acme_v_beta"}' \
    --user-id user_jane --caller-roles legal_ops
```

### 4. Run integration tests against Redshift Serverless

```bash
export LINA_REDSHIFT_DSN=postgresql://user:pass@workgroup-host:5439/dev

lina-redshift --target redshift migrate up
lina-redshift --target redshift seed
pytest -m integration -v
```

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `LINA_REDSHIFT_DSN` | when targeting Redshift | DSN for the Redshift Serverless workgroup |
| `LINA_POSTGRES_DSN` | when targeting Postgres locally | DSN for local Postgres |
| `LINA_STATEMENT_TIMEOUT_MS` | no (default 30000) | Per-query timeout |
| `LINA_LOG_FORMAT` | no (default `console`) | `json` for production, `console` for dev |
| `LINA_EXPLAIN_BEFORE_EXEC` | no | When `1`, runs `EXPLAIN` before every query and logs the plan |

## Library API

```python
import psycopg2
from lina_redshift.worker import RedshiftWorker
from lina_redshift.caller import CallerContext

conn = psycopg2.connect(os.environ["LINA_REDSHIFT_DSN"])
worker = RedshiftWorker(connection=conn)

caller = CallerContext(
    user_id="user_jane",
    roles=frozenset({"legal_ops"}),
    request_id="req_42",
)

packet = worker.run(
    query_type="matter_spend_summary",
    params={"matter_ids": ["matter_acme_v_beta"], "fiscal_periods": ["2024-Q4"]},
    caller=caller,
)
print(packet.model_dump_json(by_alias=True, indent=2))
```

## Templates

| `query_type` | Backed by | Allowed roles |
|---|---|---|
| `matter_lookup` | `vw_matter_current` | any caller with at least one role |
| `matter_spend_summary` | `mv_matter_spend_summary` | `legal_ops`, `finance`, `matter_owner` |
| `vendor_spend_summary` | `mv_vendor_spend_summary` | `legal_ops`, `finance` |
| `timekeeper_rate_analysis` | `mv_timekeeper_rate_analysis` | `legal_ops`, `finance`, `rate_admin` |
| `invoice_search` | `fact_invoice` | `legal_ops`, `finance`, `matter_owner` |
| `line_item_detail` | `fact_invoice_line_item` | `legal_ops`, `finance` |

For full parameter schemas and examples, run `lina-redshift list-templates`.

## Out of scope (deferred follow-ups)

See §11 of the design doc. Highlights:

- Subsystems A (corporate user OpenSearch), B (vendor lawyer OpenSearch), D (supervisor)
- IAM auth, AWS Secrets Manager, IaC (Terraform)
- Real ingestion pipeline (LEDES parsing, S3 → Redshift COPY)
- Row-level + column-level filtering beyond template role gates
- Custom fiscal calendars
- FX rate service integration

## Project layout

See [`docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md`](./docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md) §3.
```

- [ ] **Step 2: Run final unit suite + lint + types**

Run: `pytest -v && mypy && ruff check src tests`
Expected: green on all three.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with quickstart, env vars, and API examples"
```

---

## Task 33: Coverage Verification

**Files:** none changed.

- [ ] **Step 1: Run coverage**

```bash
coverage run -m pytest
coverage report --fail-under=80
```

Expected: 80%+ coverage on `src/lina_redshift/`.

- [ ] **Step 2: If under 80%, identify uncovered lines**

```bash
coverage report -m | grep -E "^src/lina_redshift" | sort -k4 -n
```

For each file under 80%, add targeted tests. Common gaps to address:
- Error paths in `worker.py::_execute` (timeout, connection error mapping) — write a test that injects a connection raising the relevant error.
- Edge cases in `dialect.py` (the `UnsupportedDialectError` path is already covered).
- CLI error paths (mutually exclusive flags, malformed `--params` JSON).

- [ ] **Step 3: Commit any new tests**

```bash
git add tests/
git commit -m "test: improve coverage to >=80% threshold"
```

---

## Task 34: Final Sweep + Tag v0.1.0

**Files:** none changed.

- [ ] **Step 1: Run the complete suite one more time**

```bash
pytest -v --maxfail=1
mypy
ruff check src tests
ruff format --check src tests
```

Expected: all green.

- [ ] **Step 2: Run integration tests if Redshift is available**

```bash
LINA_REDSHIFT_DSN=... pytest -m integration -v
```

- [ ] **Step 3: Tag the release**

```bash
git tag -a v0.1.0 -m "Subsystem C v0.1.0 — Redshift matter & spend worker"
```

- [ ] **Step 4: Verify success criteria from spec §12**

Confirm each item from the design doc's Success Criteria section:

- [x] All migrations apply cleanly to Postgres and (if available) Redshift.
- [x] All 6 templates execute against the seeded dataset.
- [x] Full unit suite passes in under 60 seconds.
- [x] `mypy --strict` passes.
- [x] `ruff check` passes.
- [x] CLI commands work end-to-end against both targets.
- [x] Coverage ≥ 80%.
- [x] Consumer (Subsystem D) can `from lina_redshift import RedshiftWorker, CallerContext, ResultPacket` and invoke any template.

If all items pass, Subsystem C is ready to be consumed by Subsystem D.

---

## Self-Review (writing-plans skill)

**1. Spec coverage:**

| Spec section | Covered by |
|---|---|
| §1 Goal | Tasks 1–34 (whole plan) |
| §2 Architectural decisions Q1–Q10 | Locked in throughout; no implementation deviation |
| §3 Repo layout | Task 1 (bootstrap) creates skeleton; subsequent tasks fill in |
| §4 Schema & migrations | Tasks 4–11 |
| §4.2 Dialect shim | Task 3 |
| §4.4 View/MV definitions | Task 11 |
| §5 Templates & worker | Tasks 12–22 |
| §5.4 Six templates | Tasks 14–19 |
| §5.5 13 validation rules | Task 13 (AST checker) + Task 22 (worker) |
| §5.6 ResultPacket | Task 12 |
| §5.7 Typed exceptions | Task 12 |
| §6 Seed data (3 layers) | Tasks 23, 24, 25 |
| §6.4 load_all loader | Task 23 (skeleton) + Task 26 (integration test) |
| §7 CLI (6 commands) | Tasks 27, 28, 29 |
| §8 Testing strategy | Tasks 1, 4 (Postgres fixture), 30, 31 |
| §9 Observability (`structlog`, sql_trace_id) | Task 21 + Task 22 (binding) |
| §10 Cross-subsystem ID contracts | Documented in design; consumed by named seed (Task 24) |
| §11 Out of scope | Documented in README (Task 32) |
| §12 Success criteria | Verified in Task 33 + Task 34 |

No spec gaps detected.

**2. Placeholder scan:**

No "TBD", "TODO", "implement later", "etc.", "appropriate", "similar to Task N" in implementation steps. Tasks 5–11 deliberately repeat the migration test pattern verbatim per skill guidance ("repeat the code"). Task 33 mentions "common gaps to address" with concrete examples, not vague hand-waving.

**3. Type consistency check:**

- `CallerContext` (Task 12) is consumed identically across Tasks 22, 27, 29, 30 — `user_id`, `roles`, `request_id`, `permission_tags` all used consistently.
- `ResultPacket` (Task 12) is constructed in Task 22 and asserted in Tasks 22, 27, 29, 30 with consistent field names (`metrics`, `sql_trace_id`, `row_count`, `truncated`, `result_type`).
- `ErrorPacket.from_exception` signature matches across Tasks 12 and 22.
- `QueryTemplate.build_sql` signature `(self, params: BaseModel) -> tuple[str, dict[str, Any]]` is identical across all six template implementations (Tasks 14–19).
- `MigrationRunner(connection=..., sql_dir=..., target=...)` constructor used consistently across Tasks 4, 5, 6, 7, 8, 9, 10, 11, 22, 23, 24, 25, 26, 27, 30, 31.
- `load_named_entities`, `load_billing_codes`, `load_bulk_generated`, `load_all` signatures consistent.
- `validate_template_sql` signature identical between Task 13 (definition) and Task 19 (override usage in `LineItemDetailTemplate.validate_at_import`).

No type drift detected.

---

**Plan complete.** Ready for execution.







