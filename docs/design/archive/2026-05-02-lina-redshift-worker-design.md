# LINA — Redshift Matter & Spend Worker (Subsystem C) Design

**Status:** Approved for planning
**Date:** 2026-05-02
**Source spec:** [`lina.md`](../../../lina.md) §3 "Matter and Spend Store" + §13 "Validation Requirements"
**Scope:** First of four sub-projects derived from `lina.md`. Subsystems A (corporate user OpenSearch), B (vendor lawyer OpenSearch), and D (supervisor) are deferred to their own design + plan cycles.

---

## 1. Goal

Ship a Python 3.12 package + CLI that exposes a Redshift query worker over a typed catalog of read-only templates, backed by:

- The `legal_matter_spend` schema from `lina.md` §3 (12 tables + 4 governed views/MVs).
- A two-tier test target (Postgres in Docker for unit tests, Redshift Serverless for integration).
- Deterministic test fixtures that exercise every template and materialized view.

The output is a working, testable artifact that can be imported by Subsystem D when it arrives, with no rework required.

---

## 2. Architectural Decisions (Locked)

| # | Decision | Choice | Rationale |
|---|---|---|---|
| Q1 | Project decomposition | Subsystem C first; A, B, D deferred | Each ships independently; C is the source of truth for numeric answers and the largest schema |
| Q2 | Scope of Subsystem C | Schema + worker + deterministic test fixtures | Minimum scope where MVs can be tested meaningfully without dragging in ingestion |
| Q3 | Language / runtime | Python 3.12 | Strongest SQL parsing ecosystem (`sqlglot`); mature Redshift Python client; matches likely Subsystem D stack |
| Q4 | Test database strategy | Two-tier: Postgres unit, Redshift Serverless integration | Fast inner TDD loop on Postgres, dialect fidelity check against real Redshift |
| Q5 | Query interface | Pure parameterized templates (no free-form SQL) | All 13 spec validation rules collapse to "did the input match a typed template?"; trivially auditable |
| Q6 | Deliverable shape | Library + CLI | CLI is essentially free and immediately useful for fixtures, migrations, and template debugging |
| Q7 | Migration tooling | Plain numbered `.sql` files + tiny custom runner (~60 lines) | Zero external deps; explicit; sufficient for 12 tables + 4 views |
| Q8 | Permission model | Caller context + role allowlist per template | Satisfies spec §13 spirit without inventing row-filter DSL before Subsystem D defines real callers |
| Q9 | AWS infrastructure | None — DSN-only, infra assumed external | Keeps plan focused; production hardening (IAM, IaC) becomes a follow-up plan |
| Q10 | Seed data shape | Hand-written named entities (~20) + Faker-driven bulk (~600 invoices, ~6k line items) | Named entities for golden-path assertions; bulk for aggregation/MV correctness |

Production targets remain OpenSearch + Redshift exactly as `lina.md` mandates. Postgres exists only as a local dev / unit-test stand-in for Redshift, never in production.

---

## 3. Repository Layout

Greenfield project at `/Users/mb16/My Drive (koosha.g@gmail.com)/code/lina/`.

```text
lina/
├── pyproject.toml              # ruff, mypy --strict, pytest config
├── README.md                   # quickstart, env vars, CLI examples
├── lina.md                     # existing source spec (kept for reference)
├── docs/
│   └── superpowers/
│       ├── specs/              # this design doc
│       └── plans/              # writing-plans output
├── src/
│   └── lina_redshift/
│       ├── __init__.py
│       ├── worker.py           # RedshiftWorker.run(plan, caller) -> packet
│       ├── caller.py           # CallerContext model
│       ├── packet.py           # ResultPacket model + JSON shape
│       ├── connection.py       # DSN-based connection factory
│       ├── dialect.py          # Postgres↔Redshift portability shim
│       ├── errors.py           # typed exceptions
│       ├── logging_config.py   # structlog setup
│       ├── migrations/
│       │   ├── runner.py
│       │   └── sql/
│       │       ├── 001_dim_legal_entity.sql
│       │       ├── 002_dim_cost_center.sql
│       │       ├── 003_dim_billing_code.sql
│       │       ├── 004_dim_vendor.sql
│       │       ├── 005_dim_matter.sql
│       │       ├── 006_dim_timekeeper.sql
│       │       ├── 007_fact_timekeeper_rate.sql
│       │       ├── 008_fact_invoice.sql
│       │       ├── 009_fact_invoice_line_item.sql
│       │       ├── 010_fact_matter_budget.sql
│       │       ├── 011_fact_accrual.sql
│       │       ├── 012_bridge_matter_vendor.sql
│       │       ├── 013_bridge_matter_person.sql
│       │       ├── 014_bridge_matter_allocation.sql
│       │       ├── 015_vw_matter_current.sql
│       │       ├── 016_mv_matter_spend_summary.sql
│       │       ├── 017_mv_vendor_spend_summary.sql
│       │       └── 018_mv_timekeeper_rate_analysis.sql
│       ├── templates/
│       │   ├── __init__.py             # TEMPLATE_REGISTRY
│       │   ├── base.py                 # QueryTemplate ABC + AST sanity check
│       │   ├── matter_lookup.py
│       │   ├── matter_spend_summary.py
│       │   ├── vendor_spend_summary.py
│       │   ├── timekeeper_rate_analysis.py
│       │   ├── invoice_search.py
│       │   └── line_item_detail.py
│       ├── seed/
│       │   ├── __init__.py             # load_all(connection, *, reset)
│       │   ├── named_entities.py       # hand-written golden-path data
│       │   ├── generator.py            # Faker-driven bulk generator
│       │   └── billing_codes.py        # UTBMS code seeds
│       └── cli.py                      # `lina-redshift` entry point
└── tests/
    ├── conftest.py                     # markers, pg fixture, redshift fixture
    ├── unit/                           # @pytest.mark.unit (Postgres)
    │   ├── test_dialect_shim.py
    │   ├── test_migration_runner.py
    │   ├── test_template_registry.py
    │   ├── test_template_validation.py
    │   ├── test_caller_authorization.py
    │   ├── test_matter_lookup.py
    │   ├── test_matter_spend_summary.py
    │   ├── test_vendor_spend_summary.py
    │   ├── test_timekeeper_rate_analysis.py
    │   ├── test_invoice_search.py
    │   ├── test_line_item_detail.py
    │   ├── test_worker_integration.py
    │   ├── test_seed_named_entities.py
    │   └── test_cli.py
    └── integration/                    # @pytest.mark.integration (Redshift)
        ├── test_redshift_dialect_parity.py
        └── test_redshift_smoke.py
```

### 3.1 Dependencies

**Runtime:**
`redshift-connector`, `psycopg2-binary`, `pydantic>=2`, `sqlglot`, `python-ulid`, `structlog`, `click`, `Faker`.

**Dev:**
`pytest`, `pytest-postgresql`, `mypy`, `ruff`.

### 3.2 Out-of-band assumptions

- Docker installed locally for the Postgres test fixture.
- A Redshift Serverless workgroup endpoint and database user exist when `pytest -m integration` runs. Connection details supplied via `LINA_REDSHIFT_DSN`. Provisioning is not part of this plan.

---

## 4. Schema & Migrations

### 4.1 Migration runner

`migrations/runner.py` is ~60 lines. Behavior:

1. Reads `LINA_REDSHIFT_DSN` (default) or `LINA_POSTGRES_DSN` (when targeting Postgres).
2. Creates `schema_migrations(version varchar primary key, applied_at timestamp)` if missing.
3. Lists files matching `migrations/sql/*.sql`, sorted lexicographically by filename.
4. For each file whose `version` (filename without extension) is not yet in `schema_migrations`: read text, pass through dialect shim, execute, record version + timestamp.
5. Postgres migrations run inside a transaction. Redshift migrations run statement-by-statement (some Redshift DDL does not support transactions).
6. CLI: `lina-redshift migrate up`, `lina-redshift migrate status`.

Each migration file is idempotent (`CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE VIEW`).

### 4.2 Dialect shim

`dialect.py` is ~50 lines of regex-based translation. Migration files are written in **Redshift dialect** (the production target). The shim translates only when targeting Postgres. Translations:

| Redshift syntax | Postgres translation |
|---|---|
| `DISTSTYLE AUTO`, `DISTSTYLE KEY(...)`, `DISTSTYLE EVEN`, `DISTSTYLE ALL` | strip (no-op) |
| `SORTKEY AUTO`, `SORTKEY(...)`, `COMPOUND SORTKEY(...)`, `INTERLEAVED SORTKEY(...)` | strip (no-op) |
| `ENCODE AZ64 \| LZO \| ZSTD \| RAW \| BYTEDICT \| DELTA \| MOSTLY8 \| MOSTLY16 \| MOSTLY32 \| RUNLENGTH \| TEXT255 \| TEXT32K` | strip column-level ENCODE clauses |
| `BACKUP NO`, `BACKUP YES` | strip |
| `IDENTITY(seed, step)` | replace with `GENERATED BY DEFAULT AS IDENTITY` |
| `MATERIALIZED VIEW … AUTO REFRESH YES` | strip `AUTO REFRESH YES` (Postgres MVs are manual) |
| `varchar(max)` | replace with `varchar` (unlimited in Postgres) |

Each translation has a unit test asserting input/output strings. Unsupported Redshift syntax raises `UnsupportedDialectError` rather than silently passing.

### 4.3 Schema-specific notes

- **Foreign keys** are declared in DDL for documentation and Postgres-side enforcement. Redshift treats foreign keys as advisory; tests enforce referential integrity at application level.
- **Composite keys** for bridge tables follow `lina.md` recommendations:
  - `bridge_matter_vendor`: `(matter_id, vendor_id, vendor_role)`
  - `bridge_matter_person`: `(matter_id, person_id, person_source, person_role)`
  - `bridge_matter_allocation`: `(matter_id, legal_entity_id, cost_center_id, gl_account, effective_start_date)`
- **Materialized view refresh:** Postgres requires explicit `REFRESH MATERIALIZED VIEW`, automated in `seed/__init__.py::load_all`. Redshift uses `AUTO REFRESH YES`.
- **Fiscal period:** v1 standardizes on calendar quarters (`YYYY-QN` from `to_char(date_col, 'YYYY-"Q"Q')`). Custom fiscal calendars deferred (§9 follow-up).

### 4.4 View / MV definitions

| Object | Grain | Source tables |
|---|---|---|
| `vw_matter_current` | 1 row per non-archived matter | `dim_matter` |
| `mv_matter_spend_summary` | `(matter_id, fiscal_period)` | `fact_invoice_line_item`, `dim_matter`, `fact_matter_budget` |
| `mv_vendor_spend_summary` | `(vendor_id, fiscal_period)` | `fact_invoice_line_item`, `fact_invoice` |
| `mv_timekeeper_rate_analysis` | `(timekeeper_id, vendor_id, fiscal_period)` | `fact_invoice_line_item`, `fact_timekeeper_rate` |

Each MV exposes the metric columns enumerated in `lina.md` §"Required Redshift Views / Materialized Views".

---

## 5. Templates & Worker

### 5.1 Core flow

```text
caller + query plan
  -> RedshiftWorker.run(plan, caller)
  -> resolve template by query_type            (UnknownTemplateError on miss)
  -> authorize (caller.roles ∩ template.allowed_roles)
                                               (AuthorizationError on empty)
  -> validate parameters (pydantic)            (InvalidParametersError)
  -> render parameterized SQL via template.build_sql(params)
  -> execute (named-parameter binding)         (QueryTimeoutError on timeout)
  -> normalize rows via template.shape_packet(rows)
  -> attach sql_trace_id, row_count, truncated
  -> return ResultPacket
```

### 5.2 `CallerContext`

```python
class CallerContext(BaseModel):
    user_id: str                         # required, non-empty
    roles: frozenset[str]                # required, must contain at least one role
    permission_tags: frozenset[str] = frozenset()
    request_id: str                      # propagated from upstream or generated
```

There is no implicit "anonymous" caller. Subsystem D resolves identity before invoking the worker.

### 5.3 `QueryTemplate`

```python
class QueryTemplate(ABC):
    query_type: ClassVar[str]                       # e.g. "matter_spend_summary"
    allowed_roles: ClassVar[frozenset[str]]
    Params: ClassVar[type[BaseModel]]
    default_limit: ClassVar[int]                    # auto-injected if absent
    max_limit: ClassVar[int]                        # absolute ceiling
    template_version: ClassVar[str]                 # SemVer; bump on SQL change

    @abstractmethod
    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        """Return (sql_with_named_params, param_dict). SQL uses :name binds."""

    @abstractmethod
    def shape_packet(self, rows: list[dict]) -> list[dict]:
        """Project rows to the template's allowlisted columns."""
```

### 5.4 Template registry

Six templates ship in v1.

| `query_type` | Backed by | `allowed_roles` | Notes |
|---|---|---|---|
| `matter_lookup` | `vw_matter_current` | open to any caller with at least one role (sentinel: `frozenset({"*"})`) | Lookup by `matter_id` xor `client_matter_id` xor `matter_owner_user_id`; optional `include_closed`. |
| `matter_spend_summary` | `mv_matter_spend_summary` | `legal_ops`, `finance`, `matter_owner` | Filters: `matter_id[]`, `practice_area[]`, `matter_status[]`, `fiscal_period[]`. Metrics: subset of MV columns. |
| `vendor_spend_summary` | `mv_vendor_spend_summary` | `legal_ops`, `finance` | Filters: `vendor_id[]`, `fiscal_period[]`. |
| `timekeeper_rate_analysis` | `mv_timekeeper_rate_analysis` | `legal_ops`, `finance`, `rate_admin` | Filters: `vendor_id[]`, `timekeeper_id[]`, `fiscal_period[]`, `rate_variance_threshold`. |
| `invoice_search` | `fact_invoice` | `legal_ops`, `finance`, `matter_owner` | Filters: `matter_id[]`, `vendor_id[]`, `invoice_status[]`, `invoice_date_range`, `min_amount`, `max_amount`. |
| `line_item_detail` | `fact_invoice_line_item` | `legal_ops`, `finance` | Filters: `invoice_id[]`, `matter_id[]`, `task_code[]`, `expense_code[]`, `billing_guideline_flag`, `line_item_date_range`. |

Each template's SQL targets only its declared view/MV/table. No cross-template joins. Subsystem D composes results from multiple template calls when needed.

### 5.5 Validation rules — enforcement map

The 13 rules from `lina.md` §13, mapped 1:1 in spec order:

| # | Rule (verbatim from spec) | Enforcement |
|---|---|---|
| 1 | SELECT-only queries | Templates emit only SELECT by construction. AST sanity check at import rejects non-SELECT statement roots. |
| 2 | approved schemas/views/materialized views only | AST sanity check verifies every referenced table/view name is in `APPROVED_RELATIONS = {"vw_matter_current", "mv_matter_spend_summary", "mv_vendor_spend_summary", "mv_timekeeper_rate_analysis", "fact_invoice", "fact_invoice_line_item"}`. |
| 3 | approved column allowlist | `shape_packet` projects an explicit dict per template; columns outside the allowlist never reach the `ResultPacket`. |
| 4 | row-level and column-level permission checks | v1: role gate per template (Q8 decision). Per-row and per-column policies deferred (§11 follow-up #7). |
| 5 | join-path validation | Templates select from exactly one relation each; `build_sql` outputs are AST-checked at import to confirm no FROM-clause joins. Joins live inside MV definitions, not in template SQL. |
| 6 | LIMIT enforcement for detail queries | `default_limit` is injected by the worker if absent. Caller-supplied `limit` is clamped to `max_limit`. AST sanity check confirms a `LIMIT` placeholder is present in every template SQL. |
| 7 | timeout enforcement | `statement_timeout` set on the connection at session start (Postgres and Redshift both honor this GUC). Default 30 seconds, configurable via `LINA_STATEMENT_TIMEOUT_MS`. |
| 8 | EXPLAIN before execution | Optional dev-mode flag: when `LINA_EXPLAIN_BEFORE_EXEC=1`, the worker runs `EXPLAIN <sql>` and logs the plan before execution. Default off. |
| 9 | cost guardrails | Template-level `max_limit` is the v1 cost guardrail. Cluster-side WLM rules deferred (§11 follow-up #4). |
| 10 | no DDL | AST sanity check rejects any `CREATE`, `ALTER`, `DROP`, `TRUNCATE` token in template SQL. |
| 11 | no DML | AST sanity check rejects any `INSERT`, `UPDATE`, `DELETE`, `MERGE` token in template SQL. |
| 12 | no UNLOAD | AST sanity check rejects any `UNLOAD` or `COPY` token in template SQL. |
| 13 | no external function calls | AST sanity check rejects any function call whose name is not in the explicit allowlist `ALLOWED_FUNCTIONS = {"sum", "count", "avg", "min", "max", "coalesce", "nullif", "to_char", "date_trunc", "extract", "abs", "round", "greatest", "least"}`. New functions require an allowlist update + review. |

**Defense in depth (in addition to the per-rule enforcement above):**

- Connection-level `SET default_transaction_read_only = on` and `SET transaction_read_only = on` at session start.
- The driver connection is opened with a DB user that has only `SELECT` grants on the approved relations (assumed provisioned by ops; documented in README).

The AST sanity check runs **once at module import time** for each registered template — not per query. This catches template authoring bugs at startup, not in the request path.

### 5.6 `ResultPacket`

```python
class ResultPacket(BaseModel):
    source_engine: Literal["redshift"] = "redshift"
    schema_name: Literal["legal_matter_spend"] = "legal_matter_spend"
    result_type: str                # echoes the query_type
    metrics: list[dict[str, Any]]   # rows; field names controlled by template
    sql_trace_id: str               # ULID, also present in logs
    row_count: int
    truncated: bool                 # true if max_limit was reached
```

Mirrors the example in `lina.md` §"Redshift matter and spend worker". Field name `schema_name` (not `schema`) avoids pydantic's reserved-name conflict; serialized JSON renames it back to `schema` for spec parity.

### 5.7 Typed exceptions

All raised by the worker, all caught at the boundary, all mapped to a structured error packet:

- `UnknownTemplateError` — `query_type` not in registry.
- `AuthorizationError` — caller's roles do not intersect `template.allowed_roles`.
- `InvalidParametersError` — pydantic validation failed; wraps the underlying error.
- `QueryTimeoutError` — `statement_timeout` reached.
- `RedshiftConnectionError` — driver-level connection failure.
- `WorkerInternalError` — anything else; logged with `sql_trace_id` and full stack.

---

## 6. Seed Data

### 6.1 Layer 1 — Named Entities (`seed/named_entities.py`)

Hand-written records with stable, recognizable IDs. Used by golden-path tests that assert on specific values.

Counts:
- 3 legal entities (`le_acme_us`, `le_acme_uk`, `le_acme_de`)
- 2 cost centers
- 3 vendors (`vendor_walker`, `vendor_jones`, `vendor_meridian`)
- 3 matters (`matter_acme_v_beta` litigation, `matter_acme_privacy_review` advisory, `matter_acme_employment_2023` closed employment)
- 5 timekeepers across the 3 vendors
- 6 timekeeper rates (including one expired+renewed pair)
- 4 invoices spanning 2024-Q3, 2024-Q4, 2025-Q1
- 12 line items (mix of fee + expense, mix of currencies)
- 2 budgets (across versions)
- 2 accruals
- 6 bridge_matter_vendor rows
- 8 bridge_matter_person rows
- 2 bridge_matter_allocation rows

### 6.2 Layer 2 — Bulk Generated (`seed/generator.py`)

Deterministic `Faker` generator with `Faker.seed(42)`. Idempotent: re-running with the same seed produces the same rows.

Volumes:
- 100 matters across 8 practice areas
- 25 vendors (mix of `law_firm`, `consultant`, `expert`, `ediscovery`)
- 200 timekeepers (30% Partner, 50% Associate, 20% Paralegal/Other)
- 600 invoices spanning 2023-Q1 through 2025-Q2 (8 fiscal periods)
- ~6,000 invoice line items
- 200 timekeeper rates with effective-date history
- 100 matter budgets
- 50 accruals
- ~800 bridge rows

Currency mix: 80% USD, 10% GBP, 5% EUR, 5% other. Non-USD invoices populate `usd_amount` and `fx_rate_to_usd` from a fixed FX table (~10 currencies, hard-coded constants in `generator.py`).

About 5% of line items have `billing_guideline_flag=true` to give `mv_timekeeper_rate_analysis` non-trivial data.

### 6.3 Layer 3 — Reference Data (`seed/billing_codes.py`)

Hard-coded subset of UTBMS codes. Not generated:
- ~25 task codes (L100/L200 series)
- ~10 activity codes (A100 series)
- ~15 expense codes (E100 series)

### 6.4 Loader

`seed/__init__.py::load_all(connection, *, reset: bool = False)`:

1. If `reset`: `TRUNCATE` all tables in dependency order.
2. Load billing codes.
3. Load named entities; assert no ID collision with generated.
4. Load bulk generated.
5. `REFRESH MATERIALIZED VIEW` for the four MVs (Postgres only — Redshift `AUTO REFRESH YES` handles itself).

Exposed via CLI: `lina-redshift seed [--reset] [--bulk-only | --named-only]`.

---

## 7. CLI

`lina-redshift` is a Click-based single entry point declared in `pyproject.toml` as a console script.

| Command | Purpose |
|---|---|
| `migrate up` | apply pending migrations |
| `migrate status` | list applied + pending migration versions |
| `seed [--reset] [--bulk-only \| --named-only]` | load fixtures |
| `run <query_type> --params '<json>' [--caller-roles 'r1,r2'] [--user-id <id>]` | execute a template; print `ResultPacket` JSON to stdout |
| `list-templates` | dump the registry (query_type, allowed_roles, params schema) |
| `explain <query_type> --params '<json>'` | render the SQL + run `EXPLAIN`, do not execute |

All commands read connection details from `LINA_REDSHIFT_DSN` (default) or `LINA_POSTGRES_DSN` (when `--target postgres` is passed). Output is JSON to stdout, structured logs to stderr.

---

## 8. Testing

### 8.1 Markers and config

- `@pytest.mark.unit` — runs against ephemeral Postgres in Docker via `pytest-postgresql`'s `postgresql_proc` fixture. Default suite. `pytest` runs these. Sub-second per test.
- `@pytest.mark.integration` — runs against Redshift Serverless. Skipped when `LINA_REDSHIFT_DSN` is unset. `pytest -m integration` runs these explicitly.

`pytest.ini`:

```ini
[pytest]
markers =
    unit: fast tests against Postgres (default)
    integration: slow tests against Redshift Serverless
addopts = -m unit
```

### 8.2 Fixtures

Session-scoped fixture chain:

1. `postgres` (session) — start Postgres via `pytest-postgresql`.
2. `migrated_db` (session) — apply all migrations.
3. `seeded_db` (session) — call `load_all(reset=True)`.
4. `db` (function) — start a transaction, yield connection, roll back at end.
5. `unit_worker` (function) — `RedshiftWorker(connection=db)`.
6. `legal_ops_caller`, `finance_caller`, `matter_owner_caller`, `unauthorized_caller` (function) — pre-built `CallerContext` instances.

### 8.3 Test categories

1. **Dialect shim tests** — every translation in `dialect.py` has a unit test asserting input/output strings.
2. **Migration runner tests** — apply, idempotency, status, partial-failure recovery.
3. **Template registry tests** — every registered template loads cleanly through the AST sanity check.
4. **Parameter validation tests** — pydantic rejects malformed inputs with clear errors per template.
5. **Authorization tests** — callers without required roles get `AuthorizationError`; callers with required roles pass.
6. **Per-template behavior tests** — for each of 6 templates: (a) golden-path against named entities, (b) filter combinations, (c) limit clamping, (d) empty result, (e) parameter edge cases.
7. **Worker integration tests** — full `run()` flow with caller, packet shape, `sql_trace_id` propagation, error mapping.
8. **CLI tests** — Click runner against each command, asserting exit codes and JSON output shape.
9. **Seed integrity tests** — named entities load without ID collisions; bulk generator is deterministic across two runs with the same seed.
10. **Redshift parity tests** (integration only) — apply migrations to Redshift, run each template, assert packet shape matches Postgres for the same input.

Full unit suite target: under 30 seconds on a developer laptop.

---

## 9. Observability

`structlog` with JSON renderer in production, console renderer in dev (selected by `LINA_LOG_FORMAT` env var, defaults to console).

Per-call trace fields:

| Field | Source |
|---|---|
| `sql_trace_id` | ULID generated at worker entry |
| `request_id` | from `CallerContext`, propagated upstream |
| `user_id` | from `CallerContext` |
| `query_type` | from query plan |
| `template_version` | SemVer string declared on the template; bump on SQL change |
| `duration_ms` | execution time |
| `row_count` | rows returned |
| `truncated` | whether `max_limit` was reached |
| `outcome` | `"success"` or one of the typed exception names |

`sql_trace_id` is included in `ResultPacket` (per `lina.md` §"Redshift matter and spend worker" example output) and on every log line for the call.

Errors log the full pydantic validation error or driver error stack, with `sql_trace_id` for correlation.

**Out of scope for v1** (deferred to follow-up): metrics emission (Prometheus, CloudWatch), distributed tracing (OpenTelemetry), audit log persistence.

---

## 10. Cross-Subsystem ID Contracts

Subsystem C produces and consumes IDs that other subsystems will reference. Stable formats:

| ID | Format | Notes |
|---|---|---|
| `matter_id` | ULID prefix `matter_` (e.g. `matter_01HZX9...`) | Generated in this subsystem; referenced by A (matter_owner_user_id resolves through here) and D |
| `vendor_id` | varchar, externally assigned | Same value used in OpenSearch B and Redshift C |
| `timekeeper_id` | varchar, externally assigned | Same value used in OpenSearch B and Redshift C |
| `user_id` | varchar | Sourced from Subsystem A's OpenSearch index; appears as foreign key in Redshift `dim_matter`, `fact_matter_budget`, `fact_timekeeper_rate` |
| `client_matter_id` | varchar, externally assigned | Billing-facing matter ID |

Subsystem C does not validate that `user_id` exists in Subsystem A — that is a cross-subsystem integration concern handled by Subsystem D.

---

## 11. Out of Scope (Explicit Follow-ups)

Each of these becomes its own future spec + plan cycle:

1. **Subsystem A** — `corp_user_profiles_v1` OpenSearch index + ingestion + worker.
2. **Subsystem B** — `vendor_lawyer_profiles_v1` OpenSearch index + ingestion + worker.
3. **Subsystem D** — Supervisor / router / LLM synthesis.
4. **Production hardening** — IAM auth, AWS Secrets Manager, Redshift WLM/queue config, CloudWatch metrics, OpenTelemetry tracing.
5. **Infrastructure-as-code** — Terraform module for Redshift Serverless workgroup, namespace, IAM role.
6. **Real ingestion pipeline** — LEDES 1998B/BI invoice parser, S3 → Redshift COPY, CDC from upstream legal-ops platforms (Legal Tracker, SimpleLegal).
7. **Row-level + column-level filtering** — extending Q8 from "role gate per template" to per-row/per-column policies (e.g., matter owners only see their own matters; PII columns require `pii_access`).
8. **Custom fiscal calendars** — current MV grain assumes calendar quarters.
9. **FX rate service integration** — currently uses a hard-coded fixed table.
10. **Free-form SQL escape hatch** — Q5 option (c) hybrid, gated by role.
11. **Postgres / Redshift dialect drift CI gate** — automated detection of new Redshift-only DDL added to migrations.
12. **Audit log persistence** — durable storage of every worker call beyond structlog output.

---

## 12. Success Criteria

This subsystem is complete when:

- All migrations apply cleanly to Postgres and to Redshift Serverless.
- All 6 templates execute against the seeded dataset and return non-empty `ResultPacket`s for at least one parameter combination.
- The full unit test suite passes in under 30 seconds on a developer laptop.
- The integration test suite passes against a real Redshift Serverless workgroup.
- `mypy --strict` passes on `src/`.
- `ruff check` passes.
- `lina-redshift` CLI commands work end-to-end against both targets.
- Test coverage on `src/lina_redshift/` is at least 80%.
- A consumer (Subsystem D, when it arrives) can `from lina_redshift import RedshiftWorker, CallerContext, ResultPacket` and run any template without further setup beyond migrations + seed.
