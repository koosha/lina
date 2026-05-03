# LINA — Legal Intelligence & Navigation Assistant

A read-only chat surface for lawyers. Natural-language questions go in; typed worker calls go out to three governed data stores; a synthesized answer comes back with citations. No freeform SQL or DSL ever reaches the LLM.

Project intent and the full data contract: [`lina.md`](./lina.md).

---

## Architecture

```mermaid
graph TB
    User([Lawyer])
    User -->|"natural-language question"| Chat[lina-chat CLI]

    subgraph D["Subsystem D · lina-supervisor"]
        direction TB
        Chat --> Resolver[CallerResolver]
        Resolver --> Graph["LangGraph state machine<br/>(route → execute_tools → synthesize)"]
        Graph <--> LLM[(OpenAI gpt-5.2<br/>OpenAI API)]
    end

    Graph -->|tool: query_redshift| RedshiftWorker
    Graph -->|tool: search_users| UserSearchWorker
    Graph -->|tool: search_vendors| VendorSearchWorker

    subgraph C["Subsystem C · lina-redshift"]
        RedshiftWorker --> RS[("Amazon Redshift<br/><b>legal_matter_spend</b><br/>12 tables · 4 MVs")]
    end

    subgraph A["Subsystem A · lina-users"]
        UserSearchWorker --> OS1[("Amazon OpenSearch<br/><b>corp_user_profiles_v1</b>")]
    end

    subgraph B["Subsystem B · lina-vendors"]
        VendorSearchWorker --> OS2[("Amazon OpenSearch<br/><b>vendor_lawyer_profiles_v1</b>")]
    end

    Graph -->|"streamed answer<br/>+ source packets"| User

    classDef backend fill:#1e293b,stroke:#475569,color:#e2e8f0
    classDef worker fill:#0f766e,stroke:#14b8a6,color:#f0fdfa
    classDef llm fill:#7c2d12,stroke:#ea580c,color:#fff7ed
    class RS,OS1,OS2 backend
    class RedshiftWorker,UserSearchWorker,VendorSearchWorker worker
    class LLM llm
```

**How it works.** The user asks a question. The supervisor resolves the user's `CallerContext` via Subsystem A (`user_lookup`), then enters a LangGraph loop: OpenAI (`gpt-5.2`, with optional `reasoning_effort` from `none` → `xhigh`) picks one of three tools (`query_redshift`, `search_users`, `search_vendors`) with structured `{query_type, params}` arguments matching a registered template. The matching worker validates roles, runs the bounded query, and returns a normalized `ResultPacket`. The model either calls another tool or synthesizes a final streaming answer that cites every packet it consumed. A hard cap (`max_worker_calls=8` per turn) prevents runaway loops.

Each worker is independently usable as a library or CLI — see the per-subsystem sections below.

| Subsystem | Worker | CLI | Backend | Templates | Design doc |
|---|---|---|---|---|---|
| **C** | `RedshiftWorker` | `lina-redshift` | Amazon Redshift Serverless (Postgres locally) | 6 | [redshift](./docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md) |
| **A** | `UserSearchWorker` | `lina-users` | Amazon OpenSearch | 4 | [opensearch](./docs/superpowers/specs/2026-05-02-lina-opensearch-workers-design.md) |
| **B** | `VendorSearchWorker` | `lina-vendors` | Amazon OpenSearch | 4 | [opensearch](./docs/superpowers/specs/2026-05-02-lina-opensearch-workers-design.md) |
| **D** | LangGraph + OpenAI supervisor | `lina-chat` | A + B + C | — | [supervisor](./docs/superpowers/specs/2026-05-02-lina-supervisor-design.md) |

---

## Quickstart

### Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run the unit suite

The unit tests are hermetic. C uses `pytest-postgresql` to spin up an ephemeral Postgres per session; A and B use `testcontainers[opensearch]` (Docker required — tests skip cleanly otherwise).

```bash
pytest -v
```

### Try each CLI locally

#### `lina-redshift` — matter, vendor, and timekeeper analytics

```bash
docker run -d --name lina-pg -e POSTGRES_PASSWORD=lina -p 5432:5432 postgres:16
export LINA_POSTGRES_DSN=postgresql://postgres:lina@localhost:5432/postgres

lina-redshift --target postgres migrate up
lina-redshift --target postgres seed
lina-redshift --target postgres run matter_spend_summary \
    --params '{"matter_ids": ["matter_acme_v_beta"], "fiscal_periods": ["2024-Q4"]}' \
    --user-id user_jane_smith --caller-roles legal_ops
```

#### `lina-users` and `lina-vendors` — corporate user / vendor lawyer search

```bash
export LINA_OPENSEARCH_HOST=https://search-corp.us-east-1.es.amazonaws.com
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1

lina-users indices apply && lina-users seed
lina-users run user_search --params '{"query": "privacy counsel"}' \
    --user-id user_jane_smith --caller-roles legal_ops

lina-vendors indices apply && lina-vendors seed
lina-vendors run lawyer_search --params '{"query": "California privacy litigation"}' \
    --user-id user_jane_smith --caller-roles legal_ops
```

#### `lina-chat` — the chat supervisor

```bash
export OPENAI_API_KEY=sk-...
export LINA_REDSHIFT_DSN=postgresql://user:pass@workgroup-host:5439/dev
export LINA_OPENSEARCH_HOST=https://search-corp.us-east-1.es.amazonaws.com
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1

lina-chat ask --user-id user_jane_smith \
    --query "How much did Walker bill on Acme last quarter?"

lina-chat repl --user-id user_jane_smith        # multi-turn
```

`lina-chat` lazily detects which workers are reachable and only exposes the matching tools to the LLM, so it stays usable when only Redshift or only OpenSearch is configured.

### Run the integration suites against real backends

```bash
# Redshift Serverless (8 tests)
lina-redshift --target redshift migrate up && lina-redshift --target redshift seed
pytest -m integration tests/integration/test_redshift_smoke.py -v

# AWS OpenSearch (8 tests — A + B)
lina-users indices apply && lina-users seed
lina-vendors indices apply && lina-vendors seed
pytest -m integration tests/integration/lina_users tests/integration/lina_vendors -v

# Supervisor (2 tests, VCR-replayed; cassette or live OPENAI_API_KEY required)
pytest -m integration tests/integration/lina_supervisor -v
```

Without env vars (and without committed supervisor cassettes), `pytest -m integration` collects 18 tests and skips all of them.

---

## Library API

Every worker has the same shape: `worker.run(query_type=..., params=..., caller=...) -> ResultPacket | ErrorPacket`.

```python
import os, psycopg2
from lina_core.caller import CallerContext
from lina_redshift.worker import RedshiftWorker
from lina_users.worker import UserSearchWorker
from lina_vendors.worker import VendorSearchWorker
from lina_core.opensearch import open_client, resolve_config as os_config

caller = CallerContext(
    user_id="user_jane_smith",
    roles=frozenset({"legal_ops"}),
    request_id="req_42",
)

# Redshift
rs = RedshiftWorker(connection=psycopg2.connect(os.environ["LINA_REDSHIFT_DSN"]))
packet = rs.run(
    query_type="matter_spend_summary",
    params={"matter_ids": ["matter_acme_v_beta"], "fiscal_periods": ["2024-Q4"]},
    caller=caller,
)

# OpenSearch — users
client = open_client(os_config())
users = UserSearchWorker(client=client, config=os_config())
packet = users.run(query_type="user_lookup", params={"user_id": "user_jane_smith"}, caller=caller)

# OpenSearch — vendors
vendors = VendorSearchWorker(client=client, config=os_config())
packet = vendors.run(query_type="lawyer_search", params={"query": "privacy"}, caller=caller)

print(packet.model_dump_json(by_alias=True, indent=2))
```

The supervisor (`lina_supervisor`) wraps these three workers via `WorkerHub` + LangGraph. See [`docs/superpowers/specs/2026-05-02-lina-supervisor-design.md`](./docs/superpowers/specs/2026-05-02-lina-supervisor-design.md) for the full graph and tool schemas.

---

## Templates

14 read-only templates total. Each `query_type` is parameterized by a Pydantic model and gated by a role allow-list. Run `<cli> list-templates` to dump full parameter schemas as JSON.

### Subsystem C — `lina-redshift` (6)

| `query_type` | Backed by | Allowed roles |
|---|---|---|
| `matter_lookup` | `vw_matter_current` | any role |
| `matter_spend_summary` | `mv_matter_spend_summary` | `legal_ops`, `finance`, `matter_owner` |
| `vendor_spend_summary` | `mv_vendor_spend_summary` | `legal_ops`, `finance` |
| `timekeeper_rate_analysis` | `mv_timekeeper_rate_analysis` | `legal_ops`, `finance`, `rate_admin` |
| `invoice_search` | `fact_invoice` | `legal_ops`, `finance`, `matter_owner` |
| `line_item_detail` | `fact_invoice_line_item` | `legal_ops`, `finance` |

### Subsystem A — `lina-users` (4)

| `query_type` | Backed by | Allowed roles |
|---|---|---|
| `user_lookup` | `corp_user_profiles_v1` | any role |
| `user_search` | `corp_user_profiles_v1` | any role |
| `manager_chain` | `corp_user_profiles_v1` (multi-hop) | `legal_ops`, `hr_ops` |
| `people_filter` | `corp_user_profiles_v1` | any role |

### Subsystem B — `lina-vendors` (4)

| `query_type` | Backed by | Allowed roles |
|---|---|---|
| `timekeeper_lookup` | `vendor_lawyer_profiles_v1` | any role |
| `lawyer_search` | `vendor_lawyer_profiles_v1` | any role |
| `outside_counsel_filter` | `vendor_lawyer_profiles_v1` | `legal_ops`, `finance`, `procurement` |
| `practice_area_match` | `vendor_lawyer_profiles_v1` | any role |

---

## Environment variables

### Redshift (Subsystem C)

| Variable | Required | Purpose |
|---|---|---|
| `LINA_REDSHIFT_DSN` | when targeting Redshift | DSN for the Redshift Serverless workgroup |
| `LINA_POSTGRES_DSN` | when targeting Postgres locally | DSN for local Postgres |
| `LINA_STATEMENT_TIMEOUT_MS` | no (default 30000) | Per-query timeout |
| `LINA_LOG_FORMAT` | no (default `console`) | `json` for prod, `console` for dev |
| `LINA_EXPLAIN_BEFORE_EXEC` | no | When `1`, runs `EXPLAIN` before every query and logs the plan |

### OpenSearch (Subsystems A + B share one set)

| Variable | Required | Purpose |
|---|---|---|
| `LINA_OPENSEARCH_HOST` | when targeting OpenSearch | Cluster endpoint |
| `LINA_OPENSEARCH_AUTH` | no (default `basic`) | One of `basic`, `aws_sigv4`, `none` |
| `LINA_OPENSEARCH_USER` / `LINA_OPENSEARCH_PASSWORD` | when `auth=basic` | HTTP basic credentials |
| `LINA_AWS_REGION` | when `auth=aws_sigv4` | Region for SigV4 signing |
| `LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS` | no (default 30) | Per-request timeout |

### Supervisor (Subsystem D — `lina-chat`)

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | OpenAI API key |
| `LINA_SUPERVISOR_MODEL` | no (default `gpt-5.2`) | Override the OpenAI model |
| `LINA_SUPERVISOR_REASONING_EFFORT` | no (default `none`) | One of `none`, `low`, `medium`, `high`, `xhigh`. `none` = treat as a non-reasoning chat model (fastest); higher levels improve multi-hop tool routing at higher latency + cost. Only sent to the API when not `none`. |
| `LINA_SUPERVISOR_MAX_WORKER_CALLS` | no (default 8) | Hard cap on worker calls per user turn |
| `LINA_SUPERVISOR_ROUTE_MAX_TOKENS` | no (default 2048) | Token cap for routing pass (`max_completion_tokens`) |
| `LINA_SUPERVISOR_SYNTHESIZE_MAX_TOKENS` | no (default 4096) | Token cap for synthesis pass (`max_completion_tokens`) |
| `LINA_SUPERVISOR_REQUEST_TIMEOUT_SECONDS` | no (default 60) | Per-request timeout for OpenAI |

The supervisor reuses the Redshift and OpenSearch env vars above; any worker whose env vars are unset is omitted from the tool catalog rather than failing the run.

---

## Cross-subsystem ID parity

Named seeds across A, B, and C share fixed IDs so end-to-end golden-path tests that span subsystems resolve cleanly:

- **A ↔ C** — `lina_users` named users (`user_jane_smith`, `user_alex_lee`, …) match the `matter_owner_user_id` values referenced by `lina_redshift.seed.named_entities`.
- **B ↔ C** — `lina_vendors` named timekeepers (`tk_walker_partner`, `tk_walker_associate`, `tk_jones_partner`, `tk_meridian_partner`, `tk_meridian_paralegal`) match the `dim_timekeeper` named entries in C, and the `vendor_*` IDs match `dim_vendor` entries.

Generated (bulk-seeded) test data in each subsystem uses a disjoint ID prefix so the named-seed surface is never overwritten.

---

## Quality gates

```bash
pytest -v                          # unit suite
mypy                               # strict type-check across all four subsystems
ruff check src tests               # lint
ruff format --check src tests      # formatting
coverage report --fail-under=80    # coverage gate
```

CI-ready snapshot: 303 unit tests passing, ≥91% coverage on `src/lina_redshift/`, mypy/ruff/format clean across 154 source files.

---

## Sandbox deployment

An OpenTofu module under `infra/tofu/` provisions a demo-grade hosted sandbox
on AWS. After `tofu apply` and a follow-up image build/push, `lina-chat ask`
is reachable at a public HTTPS endpoint guarded by a single shared API key.

See [`infra/tofu/README.md`](./infra/tofu/README.md) for first-time bootstrap
and [`deploy/runbook.md`](./deploy/runbook.md) for image build, migrate, seed,
and smoke-test commands.

Cost at idle: ~$28/month (OpenSearch dominates). Cost per query: ~$0.01–0.05
(OpenAI tokens dominate). Tear down via `tofu destroy` between demo sessions
to drop the bill to ~$0.

---

## Out of scope (deferred follow-ups)

See §11/§12 of each design doc. Highlights:

- IAM auth, AWS Secrets Manager, IaC (Terraform / CDK)
- Real ingestion pipelines (LEDES parsing, OpenSearch ingest, S3 → Redshift COPY)
- Row-level + column-level filtering beyond template role gates
- Custom fiscal calendars, FX rate service integration
- Persistent supervisor session storage (current `InMemorySessionStore` is per-process)
- FastAPI / HTTP service deployment of `lina-chat`
- AWS Bedrock or Azure OpenAI as alternatives to direct OpenAI API
- Hybrid retrieval (kNN on `profile_embedding` is reserved in the OpenSearch mappings)

---

## Project layout

```text
lina/
├── lina.md                              # source data contract
├── docs/superpowers/
│   ├── specs/                           # 3 design docs, one per subsystem cycle
│   └── plans/                           # 3 implementation plans
├── src/
│   ├── lina_core/                       # shared: CallerContext, ResultPacket, opensearch, logging
│   ├── lina_redshift/                   # Subsystem C — Redshift worker + CLI + seed + 18 migrations
│   ├── lina_users/                      # Subsystem A — OpenSearch corp users
│   ├── lina_vendors/                    # Subsystem B — OpenSearch vendor lawyers
│   └── lina_supervisor/                 # Subsystem D — LangGraph supervisor
└── tests/
    ├── unit/                            # 303 hermetic tests
    └── integration/                     # 18 staged tests (Redshift + OpenSearch + OpenAI VCR)
```

Per-subsystem layout details live in §3 of each design doc.
