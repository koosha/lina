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
import os
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
