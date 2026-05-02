# LINA — Read-only Workers for Legal Matter, User, and Vendor Data

LINA exposes typed catalogs of read-only query templates over three backing
stores so a chat tier can retrieve matter / spend, corporate user, and outside
counsel facts without writing freeform SQL or DSL. Project intent and full data
contract: [`lina.md`](./lina.md).

| Subsystem | Worker | Backend | Schema / index |
|---|---|---|---|
| C | `RedshiftWorker` (`lina-redshift`) | Amazon Redshift Serverless (Postgres locally for tests) | `legal_matter_spend` |
| A | `UserSearchWorker` (`lina-users`) | Amazon OpenSearch | `corp_user_profiles_v1` |
| B | `VendorSearchWorker` (`lina-vendors`) | Amazon OpenSearch | `vendor_lawyer_profiles_v1` |
| D | `lina-chat` supervisor (LangGraph + Anthropic) | the three workers above | — |

Design contracts:

- C: [`docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md`](./docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md)
- A + B: [`docs/superpowers/specs/2026-05-02-lina-opensearch-workers-design.md`](./docs/superpowers/specs/2026-05-02-lina-opensearch-workers-design.md)
- D: [`docs/superpowers/specs/2026-05-02-lina-supervisor-design.md`](./docs/superpowers/specs/2026-05-02-lina-supervisor-design.md)

## Quickstart

### 1. Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Local development

The unit suites are hermetic:

- C uses `pytest-postgresql` to spin up an ephemeral Postgres per test (Docker not required for the Postgres path itself, though it is required for some auxiliary tests).
- A and B use `testcontainers[opensearch]` to spin up a single OpenSearch container per session. Tests skip cleanly when Docker is not running.

```bash
pytest -v
```

### 3. Try the CLIs

#### Subsystem C — `lina-redshift`

```bash
docker run -d --name lina-pg -e POSTGRES_PASSWORD=lina -p 5432:5432 postgres:16
export LINA_POSTGRES_DSN=postgresql://postgres:lina@localhost:5432/postgres

lina-redshift --target postgres migrate up
lina-redshift --target postgres seed
lina-redshift --target postgres list-templates
lina-redshift --target postgres run matter_lookup \
    --params '{"matter_id": "matter_acme_v_beta"}' \
    --user-id user_jane_smith --caller-roles legal_ops
```

#### Subsystem A — `lina-users`

```bash
export LINA_OPENSEARCH_HOST=https://search-corp-users.example.us-east-1.es.amazonaws.com
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1

lina-users indices apply
lina-users seed
lina-users list-templates
lina-users run user_lookup \
    --params '{"user_id": "user_jane_smith"}' \
    --user-id user_jane_smith --caller-roles legal_ops
```

#### Subsystem B — `lina-vendors`

```bash
# Reuses the same LINA_OPENSEARCH_* env vars as Subsystem A
lina-vendors indices apply
lina-vendors seed
lina-vendors list-templates
lina-vendors run timekeeper_lookup \
    --params '{"timekeeper_id": "tk_walker_partner"}' \
    --user-id user_jane_smith --caller-roles legal_ops
```

#### Subsystem D — `lina-chat` supervisor

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export LINA_REDSHIFT_DSN=postgresql://user:pass@workgroup-host:5439/dev
export LINA_OPENSEARCH_HOST=https://search-...es.amazonaws.com
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1

lina-chat ask --user-id user_jane_smith \
    --query "How much did Walker bill on Acme last quarter?"

# Multi-turn REPL
lina-chat repl --user-id user_jane_smith
```

`lina-chat` lazily detects which workers are reachable and only exposes the
matching tools to the LLM, so it stays usable when only Redshift or only
OpenSearch is configured.

##### How the supervisor works

The supervisor is a three-node LangGraph state machine — `route` → `execute_tools` → (loop back to `route` or fall through to) `synthesize`. `route` calls Claude with the three worker tools (`query_redshift`, `search_users`, `search_vendors`); `execute_tools` dispatches each `tool_use` block via the `WorkerHub`, appends the typed `ResultPacket` as a `tool_result` block, and increments a per-turn worker-call counter. When the counter hits `LINA_SUPERVISOR_MAX_WORKER_CALLS` (default 8) the loop falls through to `synthesize`, which streams a final answer with the data already gathered. See [§5 of the supervisor design doc](./docs/superpowers/specs/2026-05-02-lina-supervisor-design.md#5-graph-topology-langgraph) for the full graph diagram.

### 4. Run integration tests against real backends

```bash
# Redshift Serverless smoke tests (8 tests)
export LINA_REDSHIFT_DSN=postgresql://user:pass@workgroup-host:5439/dev
lina-redshift --target redshift migrate up
lina-redshift --target redshift seed
pytest -m integration tests/integration/test_redshift_smoke.py -v

# AWS OpenSearch smoke tests (8 tests — A + B)
export LINA_OPENSEARCH_HOST=https://search-...es.amazonaws.com
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1
lina-users indices apply && lina-users seed
lina-vendors indices apply && lina-vendors seed
pytest -m integration tests/integration/lina_users tests/integration/lina_vendors -v

# Supervisor smoke tests (2 tests, VCR-replayed) — require either a recorded
# YAML cassette in tests/integration/lina_supervisor/cassettes/ or a live
# ANTHROPIC_API_KEY. See tests/integration/lina_supervisor/README.md for the
# recording workflow.
pytest -m integration tests/integration/lina_supervisor -v
```

Without these env vars set (and without any committed supervisor cassettes),
`pytest -m integration` collects 18 tests and skips all of them.

## Environment variables

### Redshift (Subsystem C)

| Variable | Required | Purpose |
|---|---|---|
| `LINA_REDSHIFT_DSN` | when targeting Redshift | DSN for the Redshift Serverless workgroup |
| `LINA_POSTGRES_DSN` | when targeting Postgres locally | DSN for local Postgres |
| `LINA_STATEMENT_TIMEOUT_MS` | no (default 30000) | Per-query timeout |
| `LINA_LOG_FORMAT` | no (default `console`) | `json` for production, `console` for dev |
| `LINA_EXPLAIN_BEFORE_EXEC` | no | When `1`, runs `EXPLAIN` before every query and logs the plan |

### OpenSearch (Subsystems A and B)

Both `lina-users` and `lina-vendors` share one set of OpenSearch env vars.

| Variable | Required | Purpose |
|---|---|---|
| `LINA_OPENSEARCH_HOST` | when targeting OpenSearch | Cluster endpoint (e.g. `https://search-....es.amazonaws.com`) |
| `LINA_OPENSEARCH_AUTH` | no (default `basic`) | One of `basic`, `aws_sigv4`, `none` |
| `LINA_OPENSEARCH_USER` | when `auth=basic` | HTTP basic username |
| `LINA_OPENSEARCH_PASSWORD` | when `auth=basic` | HTTP basic password |
| `LINA_AWS_REGION` | when `auth=aws_sigv4` | Region used by SigV4 signing for AWS OpenSearch |
| `LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS` | no (default 30) | Per-request timeout |

### Supervisor (Subsystem D — `lina-chat`)

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | yes | API key for the Claude model the supervisor routes through |
| `LINA_SUPERVISOR_MODEL` | no (default `claude-sonnet-4-7`) | Override the Claude model name |
| `LINA_SUPERVISOR_MAX_WORKER_CALLS` | no (default 8) | Hard cap on worker tool calls per user turn |
| `LINA_SUPERVISOR_ROUTE_MAX_TOKENS` | no (default 2048) | `max_tokens` for the routing pass |
| `LINA_SUPERVISOR_SYNTHESIZE_MAX_TOKENS` | no (default 4096) | `max_tokens` for the synthesizer pass |
| `LINA_SUPERVISOR_REQUEST_TIMEOUT_SECONDS` | no (default 60) | Per-request timeout for Anthropic calls |

The supervisor reuses the Redshift and OpenSearch env vars above to construct
its workers; any worker whose env vars are unset is omitted from the tool
catalog rather than failing the run.

## Library API

### `RedshiftWorker`

```python
import os
import psycopg2
from lina_redshift.worker import RedshiftWorker
from lina_core.caller import CallerContext

conn = psycopg2.connect(os.environ["LINA_REDSHIFT_DSN"])
worker = RedshiftWorker(connection=conn)

caller = CallerContext(
    user_id="user_jane_smith",
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

### `UserSearchWorker`

```python
from lina_core.caller import CallerContext
from lina_users.connection import open_client, resolve_config
from lina_users.worker import UserSearchWorker

config = resolve_config()
client = open_client(config)
worker = UserSearchWorker(client=client, config=config)

caller = CallerContext(
    user_id="user_jane_smith",
    roles=frozenset({"legal_ops"}),
    request_id="req_42",
)

packet = worker.run(
    query_type="user_lookup",
    params={"user_id": "user_jane_smith"},
    caller=caller,
)
print(packet.model_dump_json(by_alias=True, indent=2))
```

### `VendorSearchWorker`

```python
from lina_core.caller import CallerContext
from lina_vendors.connection import open_client, resolve_config
from lina_vendors.worker import VendorSearchWorker

config = resolve_config()
client = open_client(config)
worker = VendorSearchWorker(client=client, config=config)

caller = CallerContext(
    user_id="user_jane_smith",
    roles=frozenset({"legal_ops"}),
    request_id="req_42",
)

packet = worker.run(
    query_type="lawyer_search",
    params={"query": "privacy", "practice_areas": ["Privacy"]},
    caller=caller,
)
print(packet.model_dump_json(by_alias=True, indent=2))
```

## Templates

LINA exposes 14 read-only templates across the three workers. Each `query_type`
is parameterized by a Pydantic model and gated by a role allow-list. Run
`lina-redshift list-templates`, `lina-users list-templates`, or
`lina-vendors list-templates` to dump the full parameter schema.

### Subsystem C (`lina-redshift`) — 6 templates

| `query_type` | Backed by | Allowed roles |
|---|---|---|
| `matter_lookup` | `vw_matter_current` | any caller with at least one role |
| `matter_spend_summary` | `mv_matter_spend_summary` | `legal_ops`, `finance`, `matter_owner` |
| `vendor_spend_summary` | `mv_vendor_spend_summary` | `legal_ops`, `finance` |
| `timekeeper_rate_analysis` | `mv_timekeeper_rate_analysis` | `legal_ops`, `finance`, `rate_admin` |
| `invoice_search` | `fact_invoice` | `legal_ops`, `finance`, `matter_owner` |
| `line_item_detail` | `fact_invoice_line_item` | `legal_ops`, `finance` |

### Subsystem A (`lina-users`) — 4 templates

| `query_type` | Backed by | Allowed roles |
|---|---|---|
| `user_lookup` | `corp_user_profiles_v1` | any caller with at least one role |
| `user_search` | `corp_user_profiles_v1` | any caller with at least one role |
| `manager_chain` | `corp_user_profiles_v1` (multi-hop) | `legal_ops`, `hr_ops` |
| `people_filter` | `corp_user_profiles_v1` | any caller with at least one role |

### Subsystem B (`lina-vendors`) — 4 templates

| `query_type` | Backed by | Allowed roles |
|---|---|---|
| `timekeeper_lookup` | `vendor_lawyer_profiles_v1` | any caller with at least one role |
| `lawyer_search` | `vendor_lawyer_profiles_v1` | any caller with at least one role |
| `outside_counsel_filter` | `vendor_lawyer_profiles_v1` | `legal_ops`, `finance`, `procurement` |
| `practice_area_match` | `vendor_lawyer_profiles_v1` | any caller with at least one role |

## Cross-subsystem ID parity

Named seeds across A, B, and C share fixed IDs so end-to-end golden-path tests
that span subsystems can resolve cleanly:

- **A ↔ C:** `lina_users` named users (`user_jane_smith`, `user_alex_lee`, ...) match the `matter_owner_user_id` values referenced by `lina_redshift.seed.named_entities`.
- **B ↔ C:** `lina_vendors` named timekeepers (`tk_walker_partner`, `tk_walker_associate`, `tk_jones_partner`, `tk_meridian_partner`, `tk_meridian_paralegal`) match the `dim_timekeeper` named entries in C, and the `vendor_*` IDs match `dim_vendor` entries.

Generated (bulk-seeded) test data in each subsystem uses a disjoint ID prefix
so the named-seed surface is never overwritten.

## Final sweep

```bash
pytest -v
mypy
ruff check src tests
ruff format --check src tests
coverage report
```

## Out of scope (deferred follow-ups)

See §11/§12 of each design doc. Highlights:

- IAM auth, AWS Secrets Manager, IaC (Terraform)
- Real ingestion pipelines (LEDES parsing, OpenSearch ingest, S3 → Redshift COPY)
- Row-level + column-level filtering beyond template role gates
- Custom fiscal calendars, FX rate service integration
- Persistent supervisor session storage (current `InMemorySessionStore` is per-process)

## Project layout

See:

- [`docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md`](./docs/superpowers/specs/2026-05-02-lina-redshift-worker-design.md) §3
- [`docs/superpowers/specs/2026-05-02-lina-opensearch-workers-design.md`](./docs/superpowers/specs/2026-05-02-lina-opensearch-workers-design.md) §3
- [`docs/superpowers/specs/2026-05-02-lina-supervisor-design.md`](./docs/superpowers/specs/2026-05-02-lina-supervisor-design.md) §3
