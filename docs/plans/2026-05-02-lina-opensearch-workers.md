# LINA OpenSearch Workers (Subsystems A + B) Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build two Python 3.12 read-only worker packages — `lina_users` (Subsystem A) over `corp_user_profiles_v1` and `lina_vendors` (Subsystem B) over `vendor_lawyer_profiles_v1` — each with typed query templates, an OpenSearch index manager, deterministic seeds, and a Click CLI. Both share the existing `lina_core` for caller/packet/errors/logging.

**Architecture:** Pure parameterized templates (no free-form OpenSearch DSL); each template emits a static query body validated at import. Two-tier testing (Docker OpenSearch via testcontainers for unit, AWS OpenSearch Service for integration). Both packages cross-reference Subsystem C's named timekeepers/users for end-to-end ID parity.

**Tech Stack:** Python 3.12, pydantic v2, opensearch-py, requests-aws4auth, structlog, click, Faker, testcontainers[opensearch], pytest, mypy, ruff.

**Spec reference:** `docs/design/2026-05-02-lina-opensearch-workers-design.md`. Cross-reference `lina.md` §1, §2, §13.

**Pattern reference:** This plan deliberately mirrors `2026-05-02-lina-redshift-worker.md` (Subsystem C). Where that plan covers SQL DDL+templates, this plan covers OpenSearch mappings+queries. Engineers familiar with C will recognize the shape.

**Authorized minor deviations** (silent, no escalation needed):
- `from collections.abc import ...` over `from typing import ...` (UP035)
- `# noqa: N812` on lowercase-class imports
- Convert `out = expr; return out` to `return expr` (RET504)
- Drop forward-ref string quotes under `from __future__ import annotations` (UP037)
- `result.stdout` instead of `result.output` for Click `CliRunner` when worker emits stderr logs

**Commit authorship:** Every commit authored by `koosha <koosha.g@gmail.com>`. **No** `Co-Authored-By: Claude` or AI attribution anywhere — not in author, not in committer, not in commit body.

---

## File Structure

```text
src/
├── lina_users/                      (NEW)
│   ├── __init__.py
│   ├── connection.py                # OpenSearchConfig + client factory
│   ├── packet.py                    # UserSearchResultPacket
│   ├── worker.py                    # UserSearchWorker
│   ├── indices/runner.py + mappings/001_corp_user_profiles_v1.json
│   ├── templates/{base, user_lookup, user_search, manager_chain, people_filter}.py
│   ├── seed/{__init__, named_entities, generator}.py
│   └── cli.py
├── lina_vendors/                    (NEW)
│   ├── (parallel layout)
│   └── …
└── (lina_core, lina_redshift unchanged)

tests/unit/
├── lina_users/test_*.py             (NEW, ~10 test files)
└── lina_vendors/test_*.py           (NEW, ~10 test files)

tests/integration/
├── lina_users/test_aws_smoke.py     (NEW, skipped without LINA_OPENSEARCH_HOST)
└── lina_vendors/test_aws_smoke.py   (NEW)
```

---

## Task A0: Dependencies and Project Wiring

**Files:**
- Modify: `pyproject.toml` (add deps + console scripts)
- Modify: `mypy.ini` (extend `files` to cover both new packages)
- Create: `src/lina_users/__init__.py` (package marker)
- Create: `src/lina_vendors/__init__.py` (package marker)
- Create: `tests/unit/lina_users/__init__.py`
- Create: `tests/unit/lina_vendors/__init__.py`
- Create: `tests/integration/lina_users/__init__.py`
- Create: `tests/integration/lina_vendors/__init__.py`

- [ ] **Step 1: Add `opensearch-py>=2.7`, `requests-aws4auth>=1.2` to runtime deps and `testcontainers[opensearch]>=4.0` to dev deps in `pyproject.toml`.**
- [ ] **Step 2: Add console scripts:**
  ```toml
  [project.scripts]
  lina-redshift = "lina_redshift.cli:main"
  lina-users = "lina_users.cli:main"
  lina-vendors = "lina_vendors.cli:main"
  ```
- [ ] **Step 3: Update `mypy.ini`:** `files = src/lina_core, src/lina_redshift, src/lina_users, src/lina_vendors`.
- [ ] **Step 4: Create empty `__init__.py` for each new package and test directory.** Each `lina_users/__init__.py` and `lina_vendors/__init__.py` contains `__version__ = "0.1.0"`.
- [ ] **Step 5: Reinstall the editable package:**
  ```bash
  .venv/bin/pip install -e ".[dev]"
  ```
  Expected: `opensearch-py`, `testcontainers`, etc. installed without errors.
- [ ] **Step 6: Verify imports + toolchain:**
  ```bash
  .venv/bin/python -c "import lina_users, lina_vendors; print(lina_users.__version__, lina_vendors.__version__)"
  .venv/bin/pytest -v
  .venv/bin/mypy
  .venv/bin/ruff check src tests
  ```
  Expected: imports work, 188 prior tests still pass, mypy + ruff clean.
- [ ] **Step 7: Commit.**
  ```bash
  git -C "..." add pyproject.toml mypy.ini src/lina_users src/lina_vendors tests/unit/lina_users tests/unit/lina_vendors tests/integration/lina_users tests/integration/lina_vendors
  git -C "..." commit -m "chore: add opensearch deps and lina_users/lina_vendors package skeletons"
  ```

---

## Subsystem A — `lina_users`

The following 5 tasks (A1–A5) build Subsystem A end-to-end. Each task ends with its own commit.

### Task A1: Connection Factory + OpenSearch Test Fixture

**Files:**
- Create: `src/lina_users/connection.py`
- Modify: `tests/conftest.py` (add session-scoped opensearch fixture)
- Create: `tests/unit/lina_users/test_connection.py`

- [ ] **Step 1: Write failing tests for connection config**

`tests/unit/lina_users/test_connection.py`:
```python
"""Unit tests for lina_users connection factory."""

from __future__ import annotations

import pytest

from lina_users.connection import (
    AuthMode,
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

    cfg = resolve_config()

    assert cfg.auth_mode == "aws_sigv4"
    assert cfg.aws_region == "us-east-1"


@pytest.mark.unit
def test_resolve_config_no_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINA_OPENSEARCH_HOST", "http://localhost:9200")
    monkeypatch.setenv("LINA_OPENSEARCH_AUTH", "none")

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
```

- [ ] **Step 2: Implement `connection.py`**

```python
"""OpenSearch connection factory: basic / aws_sigv4 / none auth modes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal

AuthMode = Literal["basic", "aws_sigv4", "none"]


class MissingHostError(RuntimeError):
    """Raised when LINA_OPENSEARCH_HOST is unset."""


@dataclass(frozen=True)
class OpenSearchConfig:
    host: str
    auth_mode: AuthMode
    username: str | None = None
    password: str | None = None
    aws_region: str | None = None
    request_timeout_seconds: int = 30


def resolve_config() -> OpenSearchConfig:
    host = os.environ.get("LINA_OPENSEARCH_HOST")
    if not host:
        raise MissingHostError("LINA_OPENSEARCH_HOST is not set")
    auth_mode_str = os.environ.get("LINA_OPENSEARCH_AUTH", "basic")
    if auth_mode_str not in ("basic", "aws_sigv4", "none"):
        raise ValueError(f"Unknown LINA_OPENSEARCH_AUTH={auth_mode_str!r}")
    timeout_s = int(os.environ.get("LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS", "30"))
    return OpenSearchConfig(
        host=host,
        auth_mode=auth_mode_str,  # type: ignore[arg-type]
        username=os.environ.get("LINA_OPENSEARCH_USER"),
        password=os.environ.get("LINA_OPENSEARCH_PASSWORD"),
        aws_region=os.environ.get("LINA_AWS_REGION"),
        request_timeout_seconds=timeout_s,
    )


def open_client(config: OpenSearchConfig) -> Any:
    """Return an `opensearchpy.OpenSearch` client configured per `config`."""
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from urllib.parse import urlparse

    parsed = urlparse(config.host)
    use_ssl = parsed.scheme == "https"

    if config.auth_mode == "basic":
        if not config.username or not config.password:
            raise ValueError("basic auth requires LINA_OPENSEARCH_USER and LINA_OPENSEARCH_PASSWORD")
        return OpenSearch(
            hosts=[config.host],
            http_auth=(config.username, config.password),
            use_ssl=use_ssl,
            verify_certs=False,
            connection_class=RequestsHttpConnection,
            timeout=config.request_timeout_seconds,
        )
    if config.auth_mode == "aws_sigv4":
        if not config.aws_region:
            raise ValueError("aws_sigv4 auth requires LINA_AWS_REGION")
        from requests_aws4auth import AWS4Auth
        import boto3

        session = boto3.Session()
        creds = session.get_credentials()
        if creds is None:
            raise RuntimeError("no AWS credentials available")
        awsauth = AWS4Auth(
            creds.access_key, creds.secret_key, config.aws_region, "es",
            session_token=creds.token,
        )
        return OpenSearch(
            hosts=[config.host],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=config.request_timeout_seconds,
        )
    return OpenSearch(
        hosts=[config.host],
        use_ssl=use_ssl,
        verify_certs=False,
        timeout=config.request_timeout_seconds,
    )
```

- [ ] **Step 3: Add `opensearch_container` and `opensearch_client` session fixtures to `tests/conftest.py`** (gated to skip when Docker isn't available).

Append to existing `tests/conftest.py`:
```python
import pytest

@pytest.fixture(scope="session")
def opensearch_container() -> Any:  # type: ignore[misc]
    """Spin up a single OpenSearch container per test session."""
    try:
        from testcontainers.opensearch import OpenSearchContainer
    except ImportError:
        pytest.skip("testcontainers[opensearch] not installed")
    container = OpenSearchContainer("opensearchproject/opensearch:2.13.0").with_env(
        "discovery.type", "single-node",
    ).with_env("plugins.security.disabled", "true")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def opensearch_client(opensearch_container: Any) -> Any:  # type: ignore[misc]
    from opensearchpy import OpenSearch
    url = opensearch_container.get_url()
    client = OpenSearch([url], use_ssl=False, verify_certs=False)
    yield client
```

- [ ] **Step 4: Run tests:** `.venv/bin/pytest tests/unit/lina_users/test_connection.py -v` → 6 passed.
- [ ] **Step 5: Run full suite + mypy + ruff:** `.venv/bin/pytest -v && .venv/bin/mypy && .venv/bin/ruff check src tests`. All green.
- [ ] **Step 6: Commit.**
  ```bash
  git -C "..." add src/lina_users/connection.py tests/unit/lina_users/test_connection.py tests/conftest.py
  git -C "..." commit -m "feat(users): add OpenSearch connection factory and test container fixture"
  ```

### Task A2: Index Mapping + Runner

**Files:**
- Create: `src/lina_users/indices/__init__.py`
- Create: `src/lina_users/indices/runner.py`
- Create: `src/lina_users/indices/mappings/001_corp_user_profiles_v1.json`
- Create: `tests/unit/lina_users/test_indices_runner.py`

- [ ] **Step 1: Write the index mapping JSON**

`src/lina_users/indices/mappings/001_corp_user_profiles_v1.json`:
```json
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": {
    "properties": {
      "user_id": {"type": "keyword"},
      "employee_id": {"type": "keyword"},
      "email": {"type": "keyword"},
      "email_text": {"type": "text"},
      "first_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
      "last_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
      "display_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
      "phone_number": {"type": "keyword"},
      "mobile_number": {"type": "keyword"},
      "job_title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
      "department": {"type": "keyword"},
      "business_unit": {"type": "keyword"},
      "cost_center": {"type": "keyword"},
      "manager_user_id": {"type": "keyword"},
      "office_location_id": {"type": "keyword"},
      "corporate_address": {
        "type": "object",
        "properties": {
          "address_line_1": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
          "address_line_2": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
          "city": {"type": "keyword"},
          "state_province": {"type": "keyword"},
          "postal_code": {"type": "keyword"},
          "country_code": {"type": "keyword"},
          "full_address": {"type": "text"}
        }
      },
      "region": {"type": "keyword"},
      "country_code": {"type": "keyword"},
      "timezone": {"type": "keyword"},
      "user_status": {"type": "keyword"},
      "user_type": {"type": "keyword"},
      "roles": {"type": "keyword"},
      "permission_tags": {"type": "keyword"},
      "legal_team_role": {"type": "keyword"},
      "practice_area_focus": {"type": "keyword"},
      "created_at": {"type": "date"},
      "updated_at": {"type": "date"},
      "source_system": {"type": "keyword"}
    }
  }
}
```

- [ ] **Step 2: Write failing tests**

`tests/unit/lina_users/test_indices_runner.py`:
```python
"""Unit tests for the lina_users index runner."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lina_users.indices.runner import IndexRunner, list_pending

MAPPINGS_DIR = (
    Path(__file__).resolve().parents[3]
    / "src" / "lina_users" / "indices" / "mappings"
)


@pytest.fixture
def runner(opensearch_client: Any) -> IndexRunner:
    # Ensure clean slate between tests
    if opensearch_client.indices.exists(index="corp_user_profiles_v1"):
        opensearch_client.indices.delete(index="corp_user_profiles_v1")
    if opensearch_client.indices.exists(index="lina_users_index_state"):
        opensearch_client.indices.delete(index="lina_users_index_state")
    return IndexRunner(client=opensearch_client, mappings_dir=MAPPINGS_DIR)


@pytest.mark.unit
def test_apply_pending_creates_index(runner: IndexRunner, opensearch_client: Any) -> None:
    runner.apply_pending()
    assert opensearch_client.indices.exists(index="corp_user_profiles_v1")


@pytest.mark.unit
def test_apply_pending_records_state(runner: IndexRunner, opensearch_client: Any) -> None:
    runner.apply_pending()
    state = opensearch_client.search(
        index="lina_users_index_state",
        body={"query": {"match_all": {}}},
    )
    versions = {hit["_id"] for hit in state["hits"]["hits"]}
    assert "001_corp_user_profiles_v1" in versions


@pytest.mark.unit
def test_apply_pending_idempotent(runner: IndexRunner, opensearch_client: Any) -> None:
    runner.apply_pending()
    second = runner.apply_pending()
    assert second == []  # nothing newly applied
```

- [ ] **Step 3: Implement runner**

`src/lina_users/indices/runner.py`:
```python
"""Apply numbered .json mappings in lex order; track applied state in sidecar index."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_STATE_INDEX = "lina_users_index_state"
_STATE_INDEX_BODY: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "applied_at": {"type": "date"},
            "filename": {"type": "keyword"},
        }
    },
}


@dataclass
class IndexRunner:
    client: Any
    mappings_dir: Path

    def apply_pending(self) -> list[str]:
        self._ensure_state_index()
        already = self._already_applied()
        applied: list[str] = []
        for path in sorted(self.mappings_dir.glob("*.json")):
            version = path.stem
            if version in already:
                continue
            self._apply_one(path)
            self.client.index(
                index=_STATE_INDEX,
                id=version,
                body={"applied_at": "now", "filename": path.name},
                refresh="wait_for",
            )
            applied.append(version)
        return applied

    def _ensure_state_index(self) -> None:
        if not self.client.indices.exists(index=_STATE_INDEX):
            self.client.indices.create(index=_STATE_INDEX, body=_STATE_INDEX_BODY)

    def _already_applied(self) -> set[str]:
        result = self.client.search(
            index=_STATE_INDEX,
            body={"size": 1000, "query": {"match_all": {}}, "_source": False},
        )
        return {hit["_id"] for hit in result["hits"]["hits"]}

    def _apply_one(self, path: Path) -> None:
        body = json.loads(path.read_text())
        # Index name is filename minus the leading version prefix and .json
        # e.g. "001_corp_user_profiles_v1" -> "corp_user_profiles_v1"
        index_name = path.stem.split("_", 1)[1]
        if not self.client.indices.exists(index=index_name):
            self.client.indices.create(index=index_name, body=body)
        else:
            mappings = body.get("mappings")
            if mappings:
                self.client.indices.put_mapping(index=index_name, body=mappings)


def list_pending(*, client: Any, mappings_dir: Path) -> list[str]:
    state_index = "lina_users_index_state"
    if not client.indices.exists(index=state_index):
        return [p.stem for p in sorted(mappings_dir.glob("*.json"))]
    result = client.search(
        index=state_index,
        body={"size": 1000, "query": {"match_all": {}}, "_source": False},
    )
    already = {hit["_id"] for hit in result["hits"]["hits"]}
    return [p.stem for p in sorted(mappings_dir.glob("*.json")) if p.stem not in already]
```

- [ ] **Step 4: Run tests** → 3 passed (skipped if Docker unavailable).
- [ ] **Step 5: Run full suite + mypy + ruff.**
- [ ] **Step 6: Commit.**
  ```bash
  git -C "..." add src/lina_users/indices tests/unit/lina_users/test_indices_runner.py
  git -C "..." commit -m "feat(users): add corp_user_profiles_v1 mapping and index runner"
  ```

### Task A3: Worker Base + 4 Templates

**Files:**
- Create: `src/lina_users/packet.py`
- Create: `src/lina_users/templates/__init__.py`
- Create: `src/lina_users/templates/base.py`
- Create: `src/lina_users/templates/user_lookup.py`
- Create: `src/lina_users/templates/user_search.py`
- Create: `src/lina_users/templates/manager_chain.py`
- Create: `src/lina_users/templates/people_filter.py`
- Create: `src/lina_users/worker.py`
- Create: `tests/unit/lina_users/test_packet.py`
- Create: `tests/unit/lina_users/test_template_validation.py`
- Create: `tests/unit/lina_users/test_template_user_lookup.py`
- Create: `tests/unit/lina_users/test_template_user_search.py`
- Create: `tests/unit/lina_users/test_template_manager_chain.py`
- Create: `tests/unit/lina_users/test_template_people_filter.py`
- Create: `tests/unit/lina_users/test_worker.py`

This is the largest task in the plan. The implementer should use Subsystem C's `lina_redshift/templates/` and `worker.py` as a structural reference, replacing SQL with OpenSearch DSL. The implementer is encouraged to read [`docs/design/2026-05-02-lina-opensearch-workers-design.md`](../specs/2026-05-02-lina-opensearch-workers-design.md) §5 for the template + worker design. Key implementation guides:

**`packet.py`** subclasses `lina_core.packet.ResultPacket`/`ErrorPacket` with `source_engine="opensearch"` and `schema_name="corp_user_profiles_v1"` (mirror of `lina_redshift/packet.py`).

**`templates/base.py`** defines:
- `APPROVED_INDICES = frozenset({"corp_user_profiles_v1"})`
- `ALLOWED_TOP_LEVEL_KEYS = frozenset({"query", "size", "from", "sort", "_source", "track_total_hits"})`
- `FORBIDDEN_QUERY_CLAUSES = frozenset({"script", "script_score", "script_query", "function_score", "runtime_mappings"})`
- `validate_template_query(body, *, allowed_fields, default_size, max_size)` — recursive walk that:
  - Rejects unknown top-level keys
  - Recursively scans for any forbidden clause name as a dict key
  - Validates `_source` is `false` or a list ⊆ `allowed_fields`
  - Validates `sort` keys ⊆ `allowed_fields`
  - Ensures `size` ≤ `max_size` if present
- `UserQueryTemplate` ABC with same shape as C's `QueryTemplate` but `build_query(params) -> dict[str, Any]` and `index: ClassVar[str]`.

**`templates/__init__.py`** has `TEMPLATE_REGISTRY: dict[str, UserQueryTemplate]`, `register()`, `get_template()`, `all_templates()`. Mirrors C exactly.

**Four template files** each define `<Name>Params` (pydantic) and `<Name>Template`:

| Template | OpenSearch query | `allowed_fields` (subset shown) | `allowed_roles` |
|---|---|---|---|
| `user_lookup` | `term` on `user_id` / `email` / `employee_id`; filter `user_status` | user_id, email, display_name, department, business_unit, roles, permission_tags | `frozenset({"*"})` |
| `user_search` | `multi_match` on `display_name^2, first_name, last_name, job_title, email_text`; filter `department/business_unit/region` | same | `frozenset({"*"})` |
| `manager_chain` | iterative term lookup walking `manager_user_id` chain (multi-hop in worker, not single search) | display_name, job_title, manager_user_id | `legal_ops, hr_ops` |
| `people_filter` | `bool.must` of `terms` per filter | filterable keyword fields | `frozenset({"*"})` |

`manager_chain` is unusual: it doesn't fit one search call. The template's `build_query` returns the seed term query for `start_user_id`; the worker has special handling that loops up/down the chain (capped by `max_depth`). Document that this template is a `MultiHopUserQueryTemplate` subclass with an extra `walk_chain(client, params)` method.

**`worker.py`** is identical in shape to `lina_redshift/worker.py` — caller auth, param validation, query build, validation, search, packet shaping, error mapping. Errors map:
- `ConnectionError` (opensearch-py) → `BackendConnectionError`
- `RequestError` with `"timed_out"` in message → `QueryTimeoutError`
- Other `OpenSearchException` → `WorkerInternalError`

**Tests** mirror C's test categories: 5–8 tests per template (golden path, filter combos, size clamping, empty result, edge cases) plus 6 worker integration tests.

- [ ] **Step 1: Write all test files first (TDD).** Tests should reference fixtures `opensearch_client`, the index runner (apply at session scope), and a `seeded_client` fixture that loads named entities.
- [ ] **Step 2: Run tests → confirm fails (modules not found).**
- [ ] **Step 3: Implement `packet.py`, `templates/base.py`, `templates/__init__.py`.**
- [ ] **Step 4: Implement the four template modules; register each.**
- [ ] **Step 5: Implement `worker.py`.**
- [ ] **Step 6: Run all lina_users unit tests** → all pass.
- [ ] **Step 7: Run full suite + mypy + ruff.**
- [ ] **Step 8: Commit.**
  ```bash
  git -C "..." add src/lina_users/packet.py src/lina_users/templates src/lina_users/worker.py tests/unit/lina_users/
  git -C "..." commit -m "feat(users): add packet, template registry, four templates, and worker"
  ```

### Task A4: Seed (Named + Bulk + load_all)

**Files:**
- Create: `src/lina_users/seed/__init__.py` (with `load_all`)
- Create: `src/lina_users/seed/named_entities.py`
- Create: `src/lina_users/seed/generator.py`
- Create: `tests/unit/lina_users/test_seed_named_entities.py`
- Create: `tests/unit/lina_users/test_seed_generator.py`
- Create: `tests/unit/lina_users/test_seed_load_all.py`

- [ ] **Step 1: Hand-write `named_entities.py` with 10 named users**, including `user_jane_smith`, `user_alex_lee`, `user_sam_rodriguez` (manager of jane and alex), `user_taylor_kim`, `user_pat_brown`, `user_jordan_chen`, plus 4 more covering different `region` / `country_code` / `legal_team_role`. The IDs `user_jane_smith` and `user_alex_lee` **must** match the matter_owner_user_id values in `lina_redshift.seed.named_entities.NAMED_MATTERS` exactly.

- [ ] **Step 2: Generator (`generator.py`) — Faker.seed(42), 50 users**, IDs `user_gen_000` through `user_gen_049`. Mix of departments and statuses.

- [ ] **Step 3: `seed/__init__.py::load_all(client, *, reset)`** — bulks both layers via `helpers.bulk()`. On `reset=True`, deletes the index and re-applies the mapping first.

- [ ] **Step 4: Tests** assert correct count, idempotency, named/generated ID disjointness, cross-subsystem ID parity (`user_jane_smith` exists in both `lina_users.seed.named_entities` and `lina_redshift.seed.named_entities` as a referenced matter_owner_user_id).

- [ ] **Step 5: Run tests, full suite, mypy, ruff. All green.**

- [ ] **Step 6: Commit.**
  ```bash
  git -C "..." add src/lina_users/seed tests/unit/lina_users/test_seed_*.py
  git -C "..." commit -m "feat(users): add seed (named + Faker bulk) with cross-subsystem ID parity"
  ```

### Task A5: CLI

**Files:**
- Create: `src/lina_users/cli.py`
- Create: `tests/unit/lina_users/test_cli.py`

CLI commands (mirror `lina-redshift`):
- `lina-users indices apply | status`
- `lina-users seed [--reset] [--bulk-only | --named-only]`
- `lina-users run <query_type> --params '<json>' --user-id <id> --caller-roles 'r1,r2'`
- `lina-users explain <query_type> --params '<json>'`
- `lina-users list-templates`

`explain` returns `{sql: <opensearch body json>, explain_plan: <client.search(..., explain=True)["hits"]["hits"][0].get("_explanation")>}`. Note: keep the JSON key name `sql` despite this being OpenSearch DSL — keeps the CLI shape consistent across subsystems. (Or rename to `query` — implementer's call. Document either way.)

- [ ] **Step 1: Write tests using `CliRunner`.** Bootstrap path: indices apply → seed --named-only → exercise commands. Use `result.stdout` (Click 8.3 split semantics).
- [ ] **Step 2: Implement `cli.py`** using `lina_redshift/cli.py` as a structural template.
- [ ] **Step 3: Run tests, full suite, mypy, ruff.**
- [ ] **Step 4: Commit.**
  ```bash
  git -C "..." add src/lina_users/cli.py tests/unit/lina_users/test_cli.py
  git -C "..." commit -m "feat(users): add lina-users CLI (indices, seed, run, explain, list-templates)"
  ```

---

## Subsystem B — `lina_vendors`

Tasks B1–B5 mirror A1–A5 with the following differences:

- Index `vendor_lawyer_profiles_v1` has different fields (per `lina.md` §2): `expertise_summary` (text), `representative_matters_summary` (text), `practice_areas` (keyword[]), `bar_admissions` (keyword[]), `jurisdictions` (keyword[]), `standard_hourly_rate` (scaled_float), `effective_hourly_rate` (scaled_float), `currency_code` (keyword), `timekeeper_classification` (keyword), `years_of_experience` (integer), `rate_history` (nested), `profile_sources` (nested).
- Templates: `timekeeper_lookup`, `lawyer_search`, `outside_counsel_filter`, `practice_area_match` (per spec §5.2). `outside_counsel_filter` requires roles `legal_ops, finance, procurement`.
- `lawyer_search` and `practice_area_match` both use full-text matching on `expertise_summary` (for the latter, `match` clause; for the former, `multi_match` across name + summary).
- Named seed: 5 timekeepers — **IDs must exactly match** C's `lina_redshift.seed.named_entities.NAMED_TIMEKEEPERS`: `tk_walker_partner`, `tk_walker_associate`, `tk_jones_partner`, `tk_meridian_partner`, `tk_meridian_paralegal`. Each enriched with OpenSearch-only fields (expertise summary, practice areas, bar admissions). Vendor IDs (`vendor_walker`, `vendor_jones`, `vendor_meridian`) likewise match.
- Bulk generator: 200 timekeepers with IDs `tk_b_gen_*` and vendor IDs `vendor_b_gen_*` (disjoint from C's generated namespace).
- Worker: identical pattern to `lina_users.worker.UserSearchWorker` → `lina_vendors.worker.VendorSearchWorker`.

### Task B1: Connection Factory + Tests

Effectively a thin re-export from `lina_users.connection` since the auth model is identical. Define `lina_vendors.connection` as `from lina_users.connection import OpenSearchConfig, resolve_config, open_client, AuthMode, MissingHostError`. No new tests beyond import smoke.

Alternative: lift `OpenSearchConfig`/`resolve_config`/`open_client` into a new shared `lina_core.opensearch` submodule and have both subsystems import from there. **Recommended:** the alternative — promotes shared code on the second use, avoids `lina_users` becoming load-bearing for `lina_vendors`.

If that path is chosen, this becomes a 4-file refactor (move into `lina_core/opensearch.py`, leave `lina_users.connection` and `lina_vendors.connection` as one-line re-exports). Mirror the prior `lina_core` extraction pattern.

- [ ] **Step 1: Move `OpenSearchConfig`/`resolve_config`/`open_client`/`AuthMode`/`MissingHostError` from `src/lina_users/connection.py` to `src/lina_core/opensearch.py`.**
- [ ] **Step 2: Replace `src/lina_users/connection.py` with re-exports.**
- [ ] **Step 3: Create `src/lina_vendors/connection.py` with same re-exports.**
- [ ] **Step 4: Verify all 188+lina_users tests still pass.**
- [ ] **Step 5: Commit.**
  ```bash
  git -C "..." commit -m "refactor: lift OpenSearch connection into lina_core.opensearch"
  ```

### Task B2: Index Mapping + Runner

**Files:**
- Create: `src/lina_vendors/indices/__init__.py`
- Create: `src/lina_vendors/indices/runner.py`
- Create: `src/lina_vendors/indices/mappings/001_vendor_lawyer_profiles_v1.json`
- Create: `tests/unit/lina_vendors/test_indices_runner.py`

- [ ] **Step 1: Write the mapping JSON** per `lina.md` §2 fields (full schema), including `nested` types for `rate_history` and `profile_sources`.
- [ ] **Step 2: Lift the runner.** The `IndexRunner` in `lina_users/indices/runner.py` is generic except for the hard-coded state index name (`lina_users_index_state`). Either:
  - Generalize: pass the state index name as a constructor arg. Move to `lina_core.opensearch`.
  - Duplicate: copy verbatim into `lina_vendors/indices/runner.py` with `lina_vendors_index_state`.

  **Recommended:** generalize. Move into `lina_core.opensearch.IndexRunner` taking `state_index: str` parameter.
- [ ] **Step 3: Tests parallel A2.**
- [ ] **Step 4: Run tests, full suite, mypy, ruff. Commit.**
  ```bash
  git -C "..." commit -m "feat(vendors): add vendor_lawyer_profiles_v1 mapping and runner; generalize IndexRunner"
  ```

### Task B3: Worker Base + 4 Templates

Same pattern as A3. Largest single task. Templates:
- `timekeeper_lookup` — term on `timekeeper_id` / `email`
- `lawyer_search` — multi_match on `display_name^2, first_name, last_name, vendor_name, expertise_summary`; filters
- `outside_counsel_filter` — bool.must of terms on `vendor_id[]`, `timekeeper_classification[]`; range on `effective_hourly_rate`
- `practice_area_match` — match on `expertise_summary` plus filters

`outside_counsel_filter` enforces `currency_code` consistency: when both `min_hourly_rate` and `max_hourly_rate` are provided, params validator rejects without explicit `currency_code` filter.

- [ ] **Step 1: Tests first.**
- [ ] **Step 2: Implement modules.**
- [ ] **Step 3: All gates green.**
- [ ] **Step 4: Commit.**
  ```bash
  git -C "..." commit -m "feat(vendors): add packet, template registry, four templates, and worker"
  ```

### Task B4: Seed (Named + Bulk)

**Files:**
- Create: `src/lina_vendors/seed/{__init__,named_entities,generator}.py`
- Create: `tests/unit/lina_vendors/test_seed_*.py`

- [ ] **Step 1: Named timekeepers — 5 entries**. `timekeeper_id`, `vendor_id`, name fields **identical** to C's `NAMED_TIMEKEEPERS`. Add OpenSearch-only enrichments:
  - `tk_walker_partner`: `practice_areas: ["Litigation", "Privacy"]`, `bar_admissions: ["NY", "CA"]`, `expertise_summary: "Senior litigator with 20+ years experience in privacy and product liability matters..."`
  - And so on per spec.
- [ ] **Step 2: Bulk generator** — 200 timekeepers with `tk_b_gen_*` IDs, distinct from A's `user_gen_*`.
- [ ] **Step 3: Cross-subsystem parity test** — assert each named timekeeper_id from B is in C's `lina_redshift.seed.named_entities.NAMED_TIMEKEEPERS`.
- [ ] **Step 4: Tests, full suite, mypy, ruff, commit.**
  ```bash
  git -C "..." commit -m "feat(vendors): add seed with cross-subsystem timekeeper ID parity"
  ```

### Task B5: CLI

Same as A5 but for `lina-vendors`.

- [ ] **Step 1: Tests first.**
- [ ] **Step 2: Implement.**
- [ ] **Step 3: All gates green. Commit.**
  ```bash
  git -C "..." commit -m "feat(vendors): add lina-vendors CLI"
  ```

---

## Final Tasks

### Task F1: Integration Test Stubs (Skipped Locally)

- [ ] **Create** `tests/integration/lina_users/conftest.py` and `test_aws_smoke.py` (4 tests, skipped without `LINA_OPENSEARCH_HOST`).
- [ ] **Create** `tests/integration/lina_vendors/conftest.py` and `test_aws_smoke.py` (4 tests).
- [ ] **Commit:** `test(integration): add OpenSearch smoke tests for users and vendors workers`

### Task F2: README + Coverage Verification

- [ ] **Update** README.md with quickstart + env vars + library API for A and B.
- [ ] **Run** `coverage run -m pytest && coverage report --fail-under=80`. Add tests if needed.
- [ ] **Run** final sweep: `pytest -v`, `mypy`, `ruff check`, `ruff format --check`.
- [ ] **Commit:** `docs: extend README with users and vendors usage`

### Task F3: Tag v0.2.0 and Push

- [ ] **Tag:** `git tag -a v0.2.0 -m "Subsystems A + B v0.2.0 — corp users and vendor lawyers OpenSearch workers"`
- [ ] **Push** branch + tag to GitHub. (Tag push may need permission lift.)

---

## Self-Review

**Spec coverage:**
- §1 corp_user_profiles_v1 fields → Task A2 mapping
- §2 vendor_lawyer_profiles_v1 fields → Task B2 mapping
- §3 worker contract example shape → Tasks A3, B3 packets
- §13 13 validation rules → Tasks A3, B3 §5.5 enforcement table
- Cross-store ID contract → Tasks A4, B4 named seeds reference C's named seeds

**Type consistency:** `OpenSearchConfig`, `IndexRunner`, `UserQueryTemplate`/`VendorQueryTemplate` ABCs, `UserSearchResultPacket`/`VendorSearchResultPacket`, `UserSearchWorker`/`VendorSearchWorker` — all consistent across tasks.

**Placeholder scan:** No "TBD", no vague "appropriate error handling" — every step has actionable code or commands.

**Decisions left to implementer:** (a) generalize `IndexRunner` to `lina_core.opensearch` vs duplicate per package — recommended generalize. (b) `cli.py explain` JSON key `sql` vs `query` — implementer's call. (c) test container Docker image tag — `opensearchproject/opensearch:2.13.0` is current LTS-equivalent.

---

**Estimated commit count:** 14 (1 chore + 5 A + 5 B + 3 final).
**Estimated test count delta:** +60-80 unit tests (~250 total).
