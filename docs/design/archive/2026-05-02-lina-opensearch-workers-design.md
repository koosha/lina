# LINA — OpenSearch Workers (Subsystems A + B) Design

**Status:** Approved for planning
**Date:** 2026-05-02
**Source spec:** [`lina.md`](../../../lina.md) §1 + §2 + §13
**Scope:** Two of the four sub-projects derived from `lina.md`. Subsystem A is the corporate user profile worker; Subsystem B is the vendor lawyer / timekeeper profile worker. Both sit on Amazon OpenSearch Service. They share enough structure to plan as one cycle. Subsystem D (supervisor) remains separate.

This spec **inherits** all locked decisions from the C design at [2026-05-02-lina-redshift-worker-design.md](2026-05-02-lina-redshift-worker-design.md) where applicable. The shared `lina_core` package (extracted in commit `f61385e`) provides `CallerContext`, `ResultPacket`, `ErrorPacket`, typed exceptions, and `logging_config`. Both A and B import from there.

---

## 1. Goals

| Subsystem | Goal |
|---|---|
| **A — `lina_users`** | Read-only Python worker exposing typed templates over the `corp_user_profiles_v1` OpenSearch index, plus an idempotent bulk loader and CLI. |
| **B — `lina_vendors`** | Read-only Python worker exposing typed templates over the `vendor_lawyer_profiles_v1` OpenSearch index, plus an idempotent bulk loader and CLI. **Cross-system contract:** every `timekeeper_id` in B must match the corresponding row in Subsystem C's `dim_timekeeper`. |

Both subsystems are testable in isolation against a local OpenSearch container. Both ship with deterministic seed data that wires into Subsystem C's named entities so cross-subsystem joins (later in D) work end-to-end.

---

## 2. Architectural Decisions (Locked, Mostly by Analogy to C)

| # | Decision | Choice | Notes |
|---|---|---|---|
| 1 | Language / runtime | Python 3.12 | Same as C |
| 2 | Repo layout | Monorepo. New packages: `src/lina_users/` and `src/lina_vendors/` | Single `pyproject.toml`, single venv, three console scripts (`lina-redshift`, `lina-users`, `lina-vendors`) |
| 3 | OpenSearch client | `opensearch-py>=2.7` (official AWS-supported) | Supports both basic auth and AWS SigV4 |
| 4 | Test database strategy | Two-tier: **OpenSearch in Docker** for unit (via `testcontainers-opensearch`), **AWS OpenSearch Service** for integration | Mirrors C's Postgres+Redshift two-tier |
| 5 | Auth mechanisms | Basic auth (default for local), AWS SigV4 auth (for AWS), no auth (testcontainers) | Selected by `LINA_OPENSEARCH_AUTH` env var |
| 6 | Query interface | Pure parameterized templates; each template's `build_query()` returns a typed OpenSearch DSL body (Python dict) | Replaces SQL AST validation with **DSL schema validation** — see §5.5 |
| 7 | Permission model | Same `CallerContext` + role allowlist per template (from `lina_core`) | Identical pattern to C |
| 8 | Index management | Plain numbered `.json` files containing index settings/mappings + tiny custom runner | Mirrors C's `.sql` migration pattern, adapted for OpenSearch index lifecycle (create-or-update) |
| 9 | AWS infrastructure | None in this plan — DSN-only via env. Whoever runs integration provides an OpenSearch endpoint | Same posture as C (Q9) |
| 10 | Seed data | A: ~10 named users + 50 generated. B: ~10 named timekeepers (overlapping IDs with C's dim_timekeeper named entries) + 200 generated | Smaller than C's seed (no aggregations to test) |
| 11 | Optional vector field | Off in v1, design supports `knn_vector` field of dim 1024 with HNSW. Schema reserves the field but ingestion does not populate. | Per `lina.md` §1.5 / §2.4 |

---

## 3. Repository Layout (Additions)

```text
src/
├── lina_core/                    # existing
├── lina_redshift/                # existing
├── lina_users/                   # NEW — Subsystem A
│   ├── __init__.py
│   ├── connection.py             # OpenSearch client factory
│   ├── worker.py                 # UserSearchWorker.run(plan, caller)
│   ├── packet.py                 # UserSearchResultPacket (subclasses lina_core.ResultPacket)
│   ├── indices/
│   │   ├── runner.py             # apply create/update for *.json mappings
│   │   └── mappings/
│   │       └── 001_corp_user_profiles_v1.json
│   ├── templates/
│   │   ├── __init__.py           # registry
│   │   ├── base.py               # UserQueryTemplate ABC + DSL validator
│   │   ├── user_lookup.py        # by user_id, email, employee_id
│   │   ├── user_search.py        # by name + filters
│   │   ├── manager_chain.py      # walk reporting chain via manager_user_id
│   │   └── people_filter.py      # filter by department/business_unit/roles
│   ├── seed/
│   │   ├── __init__.py           # load_all
│   │   ├── named_entities.py     # ~10 named users incl. matter owners from C
│   │   └── generator.py          # Faker-driven (seed=42)
│   └── cli.py                    # `lina-users`
└── lina_vendors/                 # NEW — Subsystem B
    ├── __init__.py
    ├── connection.py             # may re-export from lina_users when AWS auth identical
    ├── worker.py                 # VendorSearchWorker.run(plan, caller)
    ├── packet.py                 # VendorSearchResultPacket
    ├── indices/
    │   ├── runner.py
    │   └── mappings/
    │       └── 001_vendor_lawyer_profiles_v1.json
    ├── templates/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── timekeeper_lookup.py        # by timekeeper_id
    │   ├── lawyer_search.py            # name + practice areas + jurisdictions
    │   ├── outside_counsel_filter.py   # vendor + classification + rate range
    │   └── practice_area_match.py      # match-phrase on expertise_summary
    ├── seed/
    │   ├── __init__.py
    │   ├── named_entities.py     # 5 timekeepers matching dim_timekeeper named seed
    │   └── generator.py
    └── cli.py                    # `lina-vendors`

tests/
├── unit/
│   ├── lina_users/test_*.py      # mirrors C's test layout
│   └── lina_vendors/test_*.py
└── integration/
    ├── lina_users/test_aws_smoke.py
    └── lina_vendors/test_aws_smoke.py
```

### 3.1 Dependency additions

Add to `pyproject.toml`:

```toml
dependencies = [
    # ... existing
    "opensearch-py>=2.7",
    "requests-aws4auth>=1.2",  # SigV4 helper
]

[project.optional-dependencies]
dev = [
    # ... existing
    "testcontainers[opensearch]>=4.0",
]

[project.scripts]
lina-redshift = "lina_redshift.cli:main"
lina-users = "lina_users.cli:main"
lina-vendors = "lina_vendors.cli:main"
```

---

## 4. Index Mappings

### 4.1 `corp_user_profiles_v1` (Subsystem A)

Stored as `src/lina_users/indices/mappings/001_corp_user_profiles_v1.json`. Field set comes verbatim from `lina.md` §1.

Key choices:
- `user_id`, `employee_id`, `email`, `phone_number`, `mobile_number`, `*_id`, `permission_tags`, `roles`, `practice_area_focus`: `keyword`
- `first_name`, `last_name`, `display_name`, `job_title`: `text` with `keyword` subfield (`fields.keyword`)
- `corporate_address`: `object` with the seven sub-fields per spec
- `created_at`, `updated_at`: `date` (ISO-8601)
- `profile_embedding`: omitted in v1 (reserved for follow-up)
- Settings: `number_of_shards: 1`, `number_of_replicas: 0` (single-node local; production overrides via `--shards/--replicas` flags on CLI later)

### 4.2 `vendor_lawyer_profiles_v1` (Subsystem B)

Stored as `src/lina_vendors/indices/mappings/001_vendor_lawyer_profiles_v1.json`. Field set comes verbatim from `lina.md` §2.

Key choices:
- `timekeeper_id`, `vendor_id`, `bar_admissions`, `jurisdictions`, `practice_areas`, `industries`, `currency_code`, `active_status`, `timekeeper_classification`: `keyword`
- `first_name`, `last_name`, `display_name`, `vendor_name`: `text` + `keyword` subfield
- `expertise_summary`, `representative_matters_summary`: `text` (analyzed for full-text match)
- `standard_hourly_rate`, `effective_hourly_rate`: `scaled_float` with `scaling_factor: 100`
- `years_of_experience`: `integer`
- `rate_history`: `nested` (per spec — nested so we can range-query within a single rate entry)
- `profile_sources`: `nested`
- `profile_embedding`: omitted in v1
- Settings: same as A

---

## 5. Worker Design (Both Subsystems)

### 5.1 Core flow (identical to C, just replacing SQL with OpenSearch DSL)

```text
caller + query plan
  -> Worker.run(plan, caller)
  -> resolve template by query_type
  -> authorize (caller.roles ∩ template.allowed_roles)
  -> validate parameters (pydantic)
  -> render OpenSearch DSL body via template.build_query(params)
  -> validate DSL body (schema check; see §5.5)
  -> execute (opensearch-py search call against approved index)
  -> normalize hits via template.shape_packet(hits)
  -> attach sql_trace_id, row_count, truncated
  -> return ResultPacket
```

Note: even though there's no SQL, the trace ID field is named `sql_trace_id` to keep the `ResultPacket` shape consistent with C and the spec's example output. (Or rename to `trace_id` in `lina_core` — see §10.)

### 5.2 Templates per subsystem

| Subsystem | Template | Backed by | Allowed roles | Params shape |
|---|---|---|---|---|
| **A** | `user_lookup` | `corp_user_profiles_v1` | any caller with at least one role | `user_id` xor `email` xor `employee_id`; `include_inactive: bool` |
| A | `user_search` | `corp_user_profiles_v1` | any role | `query: str` (matches name/title), filters (`department`, `business_unit`, `region`), `limit` |
| A | `manager_chain` | `corp_user_profiles_v1` | `legal_ops`, `hr_ops` | `start_user_id`, `direction` (`up` \| `down`), `max_depth` |
| A | `people_filter` | `corp_user_profiles_v1` | any role | `department[]`, `business_unit[]`, `roles[]`, `permission_tags[]`, `user_status: list[str]` |
| **B** | `timekeeper_lookup` | `vendor_lawyer_profiles_v1` | any role | `timekeeper_id` xor `email` |
| B | `lawyer_search` | `vendor_lawyer_profiles_v1` | any role | `query: str`, filters (`practice_areas[]`, `jurisdictions[]`, `bar_admissions[]`) |
| B | `outside_counsel_filter` | `vendor_lawyer_profiles_v1` | `legal_ops`, `finance`, `procurement` | `vendor_ids[]`, `classification[]`, `min_hourly_rate`, `max_hourly_rate`, `currency_code` |
| B | `practice_area_match` | `vendor_lawyer_profiles_v1` | any role | `description: str` (free text matched against `expertise_summary`), filter constraints |

8 templates total (4 per subsystem).

### 5.3 `UserQueryTemplate` / `VendorQueryTemplate` ABC

Mirrors C's `QueryTemplate`:

```python
class UserQueryTemplate(ABC):
    query_type: ClassVar[str]
    allowed_roles: ClassVar[frozenset[str]]
    Params: ClassVar[type[BaseModel]]
    default_size: ClassVar[int]   # default OpenSearch "size" (analog of LIMIT)
    max_size: ClassVar[int]
    template_version: ClassVar[str]
    index: ClassVar[str]          # always "corp_user_profiles_v1" for A

    @abstractmethod
    def build_query(self, params: BaseModel) -> dict[str, Any]:
        """Return the OpenSearch search body (dict)."""

    @abstractmethod
    def shape_packet(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Project _source rows to allowlisted fields."""

    def validate_at_import(self) -> None:
        """Run schema sanity check at module import."""
```

`VendorQueryTemplate` is identical except `index: ClassVar[str] = "vendor_lawyer_profiles_v1"`.

### 5.4 OpenSearch DSL validation (replaces SQL AST validation)

Each template's `build_query` produces a Python dict that matches the OpenSearch search-body schema. Validation rules at template-import time:

1. **Top-level keys allowlist:** only `query`, `size`, `from`, `sort`, `_source`, `track_total_hits`. No `aggs`, no `script_fields`, no `script` (script-injection vector).
2. **Forbidden clauses:** `script_score`, `script_query`, `runtime_mappings`, `function_score` (allows arbitrary scripts).
3. **`_source` allowlist:** must be either `false` or a list of field names from a per-template static `ALLOWED_FIELDS` set. Wildcard `"*"` rejected.
4. **`size` clamp:** worker injects `default_size` if absent; clamped to `max_size`.
5. **`sort` field allowlist:** only fields from `ALLOWED_FIELDS`.

Implementation: a small `validate_template_query(body: dict, *, allowed_fields: frozenset[str], default_size: int, max_size: int)` function in `lina_users/templates/base.py` (same logic in B).

This is simpler than C's sqlglot-based AST validation — OpenSearch DSL is already structured (no parsing needed).

### 5.5 Validation rules → spec §13 mapping

| Spec §13 rule | OpenSearch enforcement |
|---|---|
| 1 SELECT-only | OpenSearch `_search` API is read-only by definition; never use `_bulk`/`_update_by_query` in worker |
| 2 Approved indices/aliases | Worker hard-codes `index=template.index`; a per-package `APPROVED_INDICES` set verifies template.index belongs |
| 3 Approved column allowlist | `_source` allowlist + `shape_packet` projection |
| 4 Row/column permission | Role gate per template (v1); per-row filtering deferred |
| 5 Join-path validation | OpenSearch is single-index by API; no joins exist; passes by construction |
| 6 LIMIT enforcement | `size` clamp |
| 7 Timeout enforcement | `client.search(..., request_timeout=cfg.statement_timeout_ms/1000)` |
| 8 EXPLAIN before exec | `client.search(..., explain=True)` when `LINA_EXPLAIN_BEFORE_EXEC=1` is set |
| 9 Cost guardrails | `max_size` per template |
| 10 No DDL | Worker never calls `indices.create/put_mapping/delete` — that's the migration runner's job, never reachable from `worker.run()` |
| 11 No DML | Worker never calls `index/update/delete/bulk` |
| 12 No UNLOAD | OpenSearch has no equivalent; not applicable |
| 13 No external functions | Forbid `script` / `function_score` per §5.4 |

### 5.6 ResultPacket shape

Both subsystems subclass `lina_core.ResultPacket`:

```python
# lina_users/packet.py
class UserSearchResultPacket(_CoreResultPacket):
    source_engine: Literal["opensearch"] = "opensearch"
    schema_name: Literal["corp_user_profiles_v1"] = Field(
        default="corp_user_profiles_v1", alias="schema",
    )

# lina_vendors/packet.py
class VendorSearchResultPacket(_CoreResultPacket):
    source_engine: Literal["opensearch"] = "opensearch"
    schema_name: Literal["vendor_lawyer_profiles_v1"] = Field(
        default="vendor_lawyer_profiles_v1", alias="schema",
    )
```

---

## 6. Index Lifecycle / "Migration" Runner

OpenSearch has no DDL, but mappings can be evolved. The runner's job is:

1. Read `indices/mappings/*.json` in lex order.
2. For each file:
   - If the index doesn't exist → `client.indices.create(index=name, body=mapping)`.
   - If it exists → `client.indices.put_mapping(index=name, body=mapping["mappings"])` (settings updates require reindex; out of scope for v1).
3. Track applied versions in a sidecar index `lina_index_state` (single doc per index name, keyed by file stem).

CLI: `lina-users indices apply`, `lina-users indices status`. Same for `lina-vendors`.

---

## 7. Seed Data

### 7.1 Subsystem A — named users

10 hand-written users, including the matter owners referenced in C's named seed:
- `user_jane_smith` — Senior Counsel, Legal/Litigation, manages 2 reports
- `user_alex_lee` — Privacy Counsel, Legal/Privacy
- `user_sam_rodriguez` — VP, Legal Operations (manager of jane and alex)
- `user_taylor_kim` — Procurement Operations (legal_ops adjacent)
- `user_pat_brown` — Senior Paralegal
- `user_jordan_chen` — HR Business Partner
- ... 4 more covering different departments/regions

50 generated users via `Faker.seed(42)`.

### 7.2 Subsystem B — named timekeepers

5 hand-written timekeepers with **the exact same `timekeeper_id` and `vendor_id` values used in C's `lina_redshift/seed/named_entities.py`**:
- `tk_walker_partner`, `tk_walker_associate`, `tk_jones_partner`, `tk_meridian_partner`, `tk_meridian_paralegal`

Each enriched with OpenSearch-only fields: `expertise_summary`, `representative_matters_summary`, `practice_areas`, `bar_admissions`, etc.

200 generated timekeepers (`tk_gen_*`) — IDs disjoint from C's generated set (which uses the same prefix). To avoid collision, B's generated IDs use `tk_b_gen_*` and B's `vendor_id`s use `vendor_b_gen_*`. Documented as a known constraint: the cross-store ID contract from `lina.md` only requires the **named/preferred** IDs to match across stores; generated test data can have its own namespace.

### 7.3 Loaders

Both packages expose `load_all(client, *, reset: bool = False)` that uses the OpenSearch bulk API for performance. Per-document `_id` set to `user_id` / `timekeeper_id` for idempotency.

---

## 8. CLI

`lina-users`:
- `indices apply | status`
- `seed [--reset] [--bulk-only | --named-only]`
- `run <query_type> --params '<json>' --user-id <id> --caller-roles 'r1,r2'`
- `explain <query_type> --params '<json>'`
- `list-templates`

`lina-vendors`: same shape, against the vendor index.

---

## 9. Testing Strategy

### 9.1 Unit (Postgres → OpenSearch fixture swap)

Use `testcontainers-opensearch` to spin up an ephemeral OpenSearch container per pytest session. Auto-skip if Docker isn't running.

Fixtures:

```python
@pytest.fixture(scope="session")
def opensearch_container():
    with OpenSearchContainer("opensearchproject/opensearch:2.13.0") as os:
        yield os

@pytest.fixture(scope="session")
def opensearch_client(opensearch_container):
    from opensearchpy import OpenSearch
    return OpenSearch([opensearch_container.get_connection_url()])
```

Test categories per subsystem:
1. Index mapping applies cleanly
2. Each template's DSL validates at import
3. Caller authorization enforced
4. Per-template behavior (golden-path vs named entity, filter combos, size clamping, empty results, edge cases)
5. Worker integration (full flow, packet shape, trace ID propagation)
6. CLI tests

Target: ~20 unit tests per subsystem. Combined with C's 188, total ~228+ unit tests.

### 9.2 Integration (real AWS OpenSearch)

`@pytest.mark.integration`, skipped when `LINA_OPENSEARCH_HOST` unset. 4 smoke tests per subsystem mirroring the worker integration suite for C.

---

## 10. Cross-Store Naming Note

In Subsystem C, the trace field is `sql_trace_id`. For OpenSearch, "SQL" is wrong. We have two paths:

**Path A (chosen):** Keep field name `sql_trace_id` everywhere for consistency with `lina.md`'s example output. Generic — the name is a historical artifact across all packets.

**Path B (rejected):** Rename to `trace_id` and break C's spec parity.

Going with A. The field name is set in `lina_core.ResultPacket` and inherited by all subsystems. Documented as a naming quirk in the README.

---

## 11. Out of Scope (Follow-ups)

1. `profile_embedding` kNN ingestion + hybrid search.
2. Real ingestion pipeline (Okta/Workday/AzureAD CDC for A; vendor self-service portal for B).
3. AWS infrastructure (CDK/Terraform for OpenSearch domains).
4. IAM auth / fine-grained access control beyond template role gates.
5. Subsystem D — supervisor / router / LLM synthesis.
6. Index settings evolution (shards/replicas/refresh_interval) beyond initial create.
7. ILM (index lifecycle management) policies for time-based rolloff.

---

## 12. Success Criteria

This plan ships when:
- Both indices apply cleanly to local OpenSearch and (if available) AWS OpenSearch Service.
- All 8 templates execute against seeded data.
- Cross-subsystem ID parity verified: B's named timekeeper IDs match C's `dim_timekeeper` named seed exactly.
- Full unit suite (228+ tests) passes in under 90 seconds.
- `mypy --strict` and `ruff check` clean.
- `lina-users` and `lina-vendors` CLIs work end-to-end.
- Coverage ≥ 80% on both new packages.
