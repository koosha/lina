# LINA — Legal Intelligence & Navigation Assistant

A read-only chat surface for lawyers. Natural-language questions go in; typed
worker calls go out to three governed data stores; a synthesized answer comes
back with citations. No freeform SQL or DSL ever reaches the LLM.

**Live demo (sandbox):** [lina-web-sooty.vercel.app](https://lina-web-sooty.vercel.app)
(passphrase shared out-of-band).

Project intent and the data contract: [`docs/overview.md`](./docs/overview.md).
Schema reference for all three databases: [`docs/architecture/data-schema.md`](./docs/architecture/data-schema.md).

---

## Architecture

```mermaid
graph TB
    User([Lawyer])
    User -->|"natural-language question"| UI["web/ React SPA"]
    UI -->|"POST /ask + x-api-key"| APIGW[API Gateway HTTP API]
    APIGW --> Lambda["lina-supervisor Lambda"]

    subgraph D["Subsystem D · lina-supervisor (LangGraph)"]
        direction TB
        Lambda --> Resolver[CallerResolver]
        Resolver --> Graph["route → execute_tools → synthesize"]
        Graph <--> LLM[(gpt-5.2)]
    end

    Graph -->|tool: query_redshift| RedshiftWorker
    Graph -->|tool: search_users| UserSearchWorker
    Graph -->|tool: search_vendors| VendorSearchWorker

    subgraph C["Subsystem C · lina-redshift"]
        RedshiftWorker --> RS[("Amazon Redshift<br/><b>legal_matter_spend</b><br/>15 tables · 3 MVs · 1 view")]
    end

    subgraph A["Subsystem A · lina-users"]
        UserSearchWorker --> OS1[("Amazon OpenSearch<br/><b>corp_user_profiles_v1</b>")]
    end

    subgraph B["Subsystem B · lina-vendors"]
        VendorSearchWorker --> OS2[("Amazon OpenSearch<br/><b>vendor_lawyer_profiles_v1</b>")]
    end

    Graph -->|"answer + cited packets"| UI

    classDef backend fill:#1e293b,stroke:#475569,color:#e2e8f0
    classDef worker fill:#0f766e,stroke:#14b8a6,color:#f0fdfa
    classDef llm fill:#7c2d12,stroke:#ea580c,color:#fff7ed
    class RS,OS1,OS2 backend
    class RedshiftWorker,UserSearchWorker,VendorSearchWorker worker
    class LLM llm
```

The user asks a question. The supervisor resolves a `CallerContext` via
Subsystem A (`user_lookup`), then loops: an LLM picks one of three tools
with structured `{query_type, params}` arguments matching a registered
template; the matching worker validates roles, runs the bounded query, and
returns a normalized `ResultPacket`. The model either calls another tool or
synthesizes a final streaming answer that cites every packet it consumed
with inline `[matter]`/`[people]`/`[counsel]` source tags. A hard cap
(`max_worker_calls=8` per turn) prevents runaway loops, and any over-budget
tool calls in a single turn get a structured `WorkerCallBudgetExceeded`
placeholder so the LLM doesn't see a missing tool reply.

| Subsystem | Library | CLI | Backend | Templates |
|---|---|---|---|---|
| **C** Matter & Spend | `lina_redshift` | `lina-redshift` | Amazon Redshift Serverless (Postgres locally) | 6 |
| **A** User Profiles | `lina_users` | `lina-users` | Amazon OpenSearch | 4 |
| **B** Outside Counsel | `lina_vendors` | `lina-vendors` | Amazon OpenSearch | 4 |
| **D** Supervisor | `lina_supervisor` | `lina-chat` | A + B + C + LLM | — |

Each worker is independently usable as a library or CLI. Schema details
per subsystem live in [`docs/architecture/data-schema.md`](./docs/architecture/data-schema.md).

---

## Quickstart

The project uses [`uv`](https://docs.astral.sh/uv/) for environment +
dependency management. The committed `uv.lock` pins exact versions for
reproducibility (the Lambda Dockerfile installs from a hashed export of
the same lockfile — see [`deploy/lambda/regen-requirements.sh`](./deploy/lambda/regen-requirements.sh)).

```bash
brew install uv                     # one-time
uv sync --extra dev                  # provision .venv from uv.lock + dev extras
uv run pytest -v                     # 410 unit tests, hermetic
```

C uses `pytest-postgresql` for an ephemeral Postgres per session; A and B
use `testcontainers[opensearch]` (Docker required — tests skip cleanly
otherwise).

### Try each CLI locally

```bash
# Subsystem C — matter / vendor / timekeeper analytics (Postgres-emulated)
docker run -d --name lina-pg -e POSTGRES_PASSWORD=lina -p 5432:5432 postgres:16
export LINA_POSTGRES_DSN=postgresql://postgres:lina@localhost:5432/postgres
lina-redshift --target postgres migrate up
lina-redshift --target postgres seed
lina-redshift --target postgres run matter_spend_summary \
    --params '{"matter_ids": ["matter_acme_v_beta"], "fiscal_periods": ["2024-Q4"]}' \
    --user-id user_jane_smith --caller-roles legal_ops

# Subsystems A + B — corporate user / vendor lawyer search (real OpenSearch)
export LINA_OPENSEARCH_HOST=https://search-corp.us-east-1.es.amazonaws.com
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1
lina-users indices apply && lina-users seed
lina-vendors indices apply && lina-vendors seed
lina-users run user_search --params '{"query":"privacy counsel"}' \
    --user-id user_jane_smith --caller-roles legal_ops

# Subsystem D — supervisor (needs at least one worker reachable)
export OPENAI_API_KEY=sk-...
lina-chat ask --user-id user_jane_smith \
    --query "How much did Walker bill on Acme last quarter?"
lina-chat repl --user-id user_jane_smith       # multi-turn
```

`lina-chat` lazily detects which workers are reachable and only exposes
the matching tools to the LLM, so it stays usable when only Redshift or
only OpenSearch is configured.

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

rs = RedshiftWorker(connection=psycopg2.connect(os.environ["LINA_REDSHIFT_DSN"]))
packet = rs.run(
    query_type="matter_spend_summary",
    params={"matter_ids": ["matter_acme_v_beta"], "fiscal_periods": ["2024-Q4"]},
    caller=caller,
)

client = open_client(os_config())
users = UserSearchWorker(client=client, config=os_config())
packet = users.run(query_type="user_lookup", params={"user_id": "user_jane_smith"}, caller=caller)

vendors = VendorSearchWorker(client=client, config=os_config())
packet = vendors.run(query_type="lawyer_search", params={"query": "privacy"}, caller=caller)

print(packet.model_dump_json(by_alias=True, indent=2))
```

The supervisor (`lina_supervisor`) wraps these three workers via a
`WorkerHub` and a LangGraph state machine.

---

## Templates

14 read-only templates total. Each `query_type` is parameterized by a
Pydantic model and gated by a role allow-list. Run `<cli> list-templates`
to dump full parameter schemas as JSON.

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
| `LINA_STATEMENT_TIMEOUT_MS` | no (default `30000`) | Per-query timeout |
| `LINA_LOG_FORMAT` | no (default `console`) | `json` for prod, `console` for dev |
| `LINA_EXPLAIN_BEFORE_EXEC` | no | When `1`, runs `EXPLAIN` before every query and logs the plan |

### OpenSearch (Subsystems A + B share one set)

| Variable | Required | Purpose |
|---|---|---|
| `LINA_OPENSEARCH_HOST` | when targeting OpenSearch | Cluster endpoint |
| `LINA_OPENSEARCH_AUTH` | no (default `basic`) | One of `basic`, `aws_sigv4`, `none` |
| `LINA_OPENSEARCH_USER` / `LINA_OPENSEARCH_PASSWORD` | when `auth=basic` | HTTP basic credentials |
| `LINA_AWS_REGION` | when `auth=aws_sigv4` | Region for SigV4 signing |
| `LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS` | no (default `30`) | Per-request timeout |

### Supervisor (Subsystem D — `lina-chat`)

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | OpenAI API key |
| `LINA_SUPERVISOR_MODEL` | no (default `gpt-5.2`) | Override the model |
| `LINA_SUPERVISOR_REASONING_EFFORT` | no (default `none`) | One of `none`, `low`, `medium`, `high`, `xhigh`. Higher levels improve multi-hop tool routing at higher latency + cost. |
| `LINA_SUPERVISOR_MAX_WORKER_CALLS` | no (default `8`) | Hard cap on worker calls per user turn |
| `LINA_SUPERVISOR_ROUTE_MAX_TOKENS` | no (default `2048`) | Token cap for the routing pass |
| `LINA_SUPERVISOR_SYNTHESIZE_MAX_TOKENS` | no (default `4096`) | Token cap for the synthesis pass |
| `LINA_SUPERVISOR_REQUEST_TIMEOUT_SECONDS` | no (default `25`) | Per-request timeout for the LLM client. Sized to fit inside API Gateway's 30 s integration timeout. |

### Lambda-only (set by Tofu, not in dev)

| Variable | Purpose |
|---|---|
| `LINA_REDSHIFT_RUNTIME_SECRET_ARN` | Read-only `lina_app_readonly` user credentials. Preferred over the admin secret. |
| `LINA_REDSHIFT_SECRET_ARN` | Admin secret — fallback during the runtime-user cutover. |
| `LINA_OPENAI_SECRET_ARN` | OpenAI key. Set via `aws secretsmanager put-secret-value` after `tofu apply` (never written by Tofu). |
| `LINA_REDSHIFT_HOST`, `LINA_REDSHIFT_CONNECT_TIMEOUT` | Redshift connection knobs. |
| `LINA_MAX_BODY_BYTES`, `LINA_MAX_QUERY_CHARS`, `LINA_MAX_HISTORY_TURNS`, `LINA_MAX_HISTORY_MESSAGE_CHARS`, `LINA_MAX_TOTAL_HISTORY_CHARS` | Request input caps; defaults are sandbox-friendly. |

---

## Cross-subsystem ID parity

Named seeds across A, B, and C share fixed IDs so end-to-end tests that
span subsystems resolve cleanly:

- **A ↔ C** — `lina_users` named users (`user_jane_smith`, `user_alex_lee`, …) match the `matter_owner_user_id` values in `lina_redshift.seed.named_entities`.
- **B ↔ C** — `lina_vendors` named timekeepers (`tk_walker_partner`, …) match `dim_timekeeper`; `vendor_*` IDs match `dim_vendor`.

Generated bulk seed data uses a disjoint ID prefix so the named-seed
surface is never overwritten.

---

## Quality gates

```bash
uv run pytest -v                          # 410 unit tests
uv run mypy                               # strict type-check across all four subsystems
uv run ruff check src tests               # lint
uv run ruff format --check src tests      # formatting
```

CI: `.github/workflows/ci-integration.yml` runs the integration suite
against the dedicated `lina-ci` AWS environment on every PR that touches
schema, templates, seed, IaC, supervisor, or dependencies. Auth via GitHub
OIDC (no static keys in GitHub Secrets). `.github/workflows/ci-lockfile-check.yml`
verifies the Lambda's pinned `requirements.txt` is in sync with `uv.lock`.

---

## Sandbox deployment

OpenTofu under [`infra/tofu/`](./infra/tofu/) provisions the demo-grade
sandbox: API Gateway HTTP API → Lambda container (Python 3.12) → Redshift
Serverless + OpenSearch. Static SPA at [`web/`](./web/) ships to Vercel.
A separate API Gateway authorizer Lambda checks the shared `x-api-key`
against Secrets Manager. The chat Lambda runs as `lina_app_readonly` —
read-only against Redshift; admin credentials are reserved for migrations
and seed via the local CLI.

| Component | Where |
|---|---|
| Tofu module | [`infra/tofu/README.md`](./infra/tofu/README.md) |
| Sandbox bring-up + cutover steps | [`docs/runbooks/deploy.md`](./docs/runbooks/deploy.md) |
| CI environment provisioning | [`docs/runbooks/ci.md`](./docs/runbooks/ci.md) |
| Frontend (React + Vite) | [`web/README.md`](./web/README.md) |
| UI deployment plan (Vercel + alternatives) | [`docs/plans/ui-deployment.md`](./docs/plans/ui-deployment.md) |

After `tofu apply`, the operator runs:

1. `aws secretsmanager put-secret-value` for the OpenAI key (Tofu manages the secret container; the value lives out-of-band).
2. `lina-redshift bootstrap-runtime-user --put-secret-arn …` to create the read-only DB user.
3. `aws sns subscribe …` to receive CloudWatch alarms (Lambda errors, p95 duration > 25 s, 5xx, authorizer failures).
4. Build + push the Lambda image; `lambda update-function-code`.
5. `./scripts/post-deploy-smoke.sh` — eight checks against the live URL.

Cost at idle: ~$28/month (OpenSearch dominates). Cost per query: ~$0.01–0.05
(LLM tokens dominate). Tear down with `tofu destroy` between demo
sessions.

---

## Project layout

```text
lina/
├── README.md                  # this file
├── docs/                      # all docs — see docs/README.md for the index
│   ├── overview.md            # original brief + data contract
│   ├── architecture/          # canonical schema reference
│   ├── known-issues.md
│   ├── runbooks/              # deploy.md, ci.md
│   ├── plans/                 # active forward-looking work
│   │   └── archive/           # completed plans (historical record)
│   └── design/archive/        # original design specs (frozen snapshot)
├── design-handoff/            # frozen UI wireframes (HANDOFF.md + JSX/CSS)
├── src/
│   ├── lina_core/             # shared: CallerContext, ResultPacket, opensearch, logging
│   ├── lina_redshift/         # Subsystem C — worker, CLI, seed, 18 migrations, runtime-user bootstrap
│   ├── lina_users/            # Subsystem A — OpenSearch corp users
│   ├── lina_vendors/          # Subsystem B — OpenSearch vendor lawyers
│   └── lina_supervisor/       # Subsystem D — LangGraph supervisor + Lambda handler
├── tests/                     # 410 unit + 18 staged integration
├── infra/tofu/                # OpenTofu sandbox + CI modules
├── deploy/lambda/             # container Dockerfile + entry shim + pinned requirements
├── scripts/                   # ci-*.sh helpers + post-deploy-smoke.sh
└── web/                       # React SPA (Vite + TypeScript)
```
