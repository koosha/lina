# LINA Remediation Plan — 2026-05-04

## Context

An external review of the repo (`lina-remediation-plan-for-coding-agent.md`)
produced 21 numbered findings across P0/P1/P2 priorities. This file is my
own assessment after reading the actual code today, including:

- which findings are **still true** vs. already closed (notably: PR #3
  partially closed P0.4 by embedding param schemas in the system prompt)
- which are blockers for the **stated current goal** (1–2 trusted demo
  users hitting `https://lina-web-sooty.vercel.app`) vs. blockers for any
  graduation beyond that
- a concrete ordering with file paths, expected diff size, and what to
  test

Goal of the remediation: make the existing sandbox safer, more
deterministic, and easier to operate. **Do not** redesign the
architecture, swap data stores, or build multi-tenant auth — those are
out of scope and clearly flagged as non-goals in the review.

---

## Verified state today (from a fresh code read)

| Review item | Status | Evidence |
| --- | --- | --- |
| P0.1 — browser API key, `user_id` from body | True. Documented as sandbox-grade. Passphrase + key gate is intentional. | `web/src/lib/api.ts`, `infra/tofu/lambda_authorizer/handler.py` (header-only check) |
| P0.2 — Redshift `0.0.0.0/0:5439` ingress | True. Comment in `networking.tf:85-91` flags it as sandbox-only. | `infra/tofu/networking.tf:92-100`, `infra/tofu/lambda.tf:165-199` (no `vpc_config`) |
| P0.3 — chat Lambda uses Redshift admin creds | True. Reads admin secret ARN. No read-only role exists. | `lambda_handler.py:58-68`, env in `lambda.tf:181` |
| P0.4 — opaque tool params | **Partially closed** by PR #3. Tool definitions still expose `params: object`, but the system prompt now embeds per-template `Params.model_json_schema()` under `TOOL PARAMS SCHEMAS`. 14 query_types listed. Live-verified working. | `tools.py:50-79`, `system_prompt.py:103-127` |
| P0.5 — API GW 30s vs Lambda 60s, no client timeouts | True. `OpenAI()` instantiated with no timeout. `psycopg2.connect()` has no `connect_timeout`. `config.request_timeout_seconds=60` exists but is **never read**. | `lambda_handler.py:71-75,104`, `config.py:50` |
| P1.1 — DSN built by f-string | True. Special chars in the admin password would break. | `lambda_handler.py:58-68` |
| P1.2 — shared connection factory not used | `lina_redshift/connection.py:open_connection()` applies `statement_timeout` and `default_transaction_read_only` via GUC, but supervisor and CLI paths bypass it and call `psycopg2.connect()` directly. | `lambda_handler.py:104`, `cli.py:52` |
| P1.3 — no rollback on Redshift errors | True. `worker.py:130-141` re-raises but never calls `self._conn.rollback()`. | `src/lina_redshift/worker.py:130-141` |
| P1.4 — call budget checked AFTER dispatch | True. The graph executes all `tool_calls` returned in one turn, then increments `worker_call_count` once. If LLM returns 5 calls and `max_worker_calls=3`, all 5 run. | `graph.py:106-142` (loop), `:172-178` (cap check fires next turn only) |
| P1.5 — missing backend | Mixed. Lambda's `_build_workers_default` wraps OpenSearch in try/except (None on failure) but builds Redshift unconditionally. `WorkerHub.dispatch` calls `.run()` on potentially-None workers without null-check → `AttributeError`. CLI returns `None` for any missing env var. | `lambda_handler.py:78-115`, `workers.py:23-63` |
| P1.6 — `str(exc)` in 500 body | True. `_error_response(500, str(exc))` at `lambda_handler.py:212-214`. | quoted above |
| P1.7 — no input limits | True. No body-size, query-length, or per-message-length caps. Only `_MAX_HISTORY_TURNS=20` on `system_prompt._clean_history`. | `lambda_handler.py:140-150`, `system_prompt.py:180-199` |
| P1.8 — OpenAI key in TF state | True. `aws_secretsmanager_secret_version.openai_api_key` gets `secret_string = jsonencode({api_key = var.openai_api_key})`, so the value lands in state. | `infra/tofu/secrets.tf:8-11` |
| P2.1 — Dockerfile installs from broad `requirements.txt` | True. `deploy/lambda/requirements.txt` uses `>=` lower bounds; `uv.lock` exists but isn't used by the Dockerfile. | `deploy/lambda/Dockerfile:7-8`, `deploy/lambda/requirements.txt` |
| P2.2 — mutable image tags + `lifecycle.ignore_changes` | True. `image_uri` is `:v1.1.0` style; the lifecycle block prevents tofu from drifting. CI uses tag, not digest. | `lambda.tf:169,194-198` |
| P2.3 — doc drift | Mixed. `docs/architecture/data-schema.md` was just added (correct). Some older docs still imply IaC/Secrets Manager are out of scope. | various |
| P2.4 — UI uses heuristic for source mapping | True. `web/src/lib/sources.ts:packetToSource` disambiguates two `opensearch` workers by `result_type` keyword matching. `ResultPacket` has `source_engine` + `schema_name` but no stable `source_id`. | `web/src/lib/sources.ts:54-68`, packet defs in each subsystem |
| P2.5 — test coverage skewed | Out-of-date. Supervisor has 62 unit tests across 11 files (covers caller, CLI, config, graph routing, lambda handler, packet, session, synthesizer, **system prompt** — added in PR #3, **tools** — also there, workers dispatch). Real gaps: no UI tests, only 2 integration smoke tests for the supervisor. | `tests/unit/lina_supervisor/` |

---

## What this plan does NOT do

- No new auth system. The passphrase + browser-shipped API key is
  acceptable for the stated 1–2 trusted-user demo. Real auth is a
  separate project once the demo audience grows.
- No VPC migration. Same reasoning. The risk of public Redshift ingress
  is bounded by the API key gate and the fact that the Redshift workgroup
  has no production data.
- No Cognito, no BFF, no platform redesign.
- No frontend rewrite.

---

## Wave-by-wave plan

Each wave is sized to fit a single PR, with regression tests, a clear
verification step, and a one-line rollback recipe.

### Wave 1 — Reliability quick wins (one PR, ~half day)

Four tightly-scoped fixes that close real bugs in the request path. All
have small diffs and clear unit tests.

1. **P1.3 — rollback after Redshift errors.** In
   `src/lina_redshift/worker.py` `_execute()`, wrap the `try` in a
   `try/except/else/finally` so that *any* exception (not just psycopg2
   ones) causes `self._conn.rollback()` before re-raising. Test: simulate
   a `cur.execute` that raises, then immediately run a known-good query
   on the same connection and assert it succeeds.

2. **P1.4 — call budget enforced before dispatch.** In
   `src/lina_supervisor/graph.py` `_make_execute_tools_node`, compute
   `remaining = max_worker_calls - state["worker_call_count"]` at the
   top, slice `tool_calls[:remaining]`, dispatch only those, set
   `truncated=True` if anything was dropped, and synthesize a placeholder
   tool message for each dropped `tool_call_id` so the LLM doesn't see a
   missing reply. Test: feed an assistant turn with 5 tool calls and
   `max_worker_calls=2`; assert only 2 `hub.dispatch` calls and
   `truncated=True`.

3. **P1.5 — null-check workers on dispatch.** In
   `src/lina_supervisor/workers.py:WorkerHub.dispatch`, return a
   `BackendUnavailableError` packet when the targeted worker is `None`.
   Add a simple `BackendUnavailableError` class to `lina_supervisor/packet.py`
   alongside the existing error packets. Test: build a hub with
   `redshift_worker=None`, dispatch, assert the packet shape.

4. **P1.6 — safe Lambda errors.** Change
   `lambda_handler.handler`'s catch-all to log
   `_LOG.exception("...")` (already done) but return `_error_response(500,
   "Internal server error")` plus `request_id`. Stop interpolating
   `str(exc)`. Test: monkey-patch the graph to raise an exception with
   sensitive content, assert the 500 body does not contain that content.

**Files changed:**
- `src/lina_redshift/worker.py`
- `src/lina_supervisor/graph.py`
- `src/lina_supervisor/workers.py`
- `src/lina_supervisor/packet.py`
- `src/lina_supervisor/lambda_handler.py`
- `tests/unit/lina_redshift/test_worker.py`
- `tests/unit/lina_supervisor/test_graph_routing.py`
- `tests/unit/lina_supervisor/test_workers_dispatch.py`
- `tests/unit/lina_supervisor/test_lambda_handler.py`

**Verification:** `pytest tests/unit -q` green; live curl with a
deliberately bad query confirms the 500 body no longer contains stack
traces.

---

### Wave 2 — Connection lifecycle and timeouts (one PR, ~half day)

Closes P0.5, P1.1, P1.2 together because they're all about how the
Lambda talks to Redshift and OpenAI.

1. **Use the existing `lina_redshift.connection.open_connection`
   factory** in `lambda_handler._build_workers_default` and
   `cli._build_redshift_worker`. The factory already applies
   `statement_timeout` and `default_transaction_read_only` GUCs. Pass
   the admin secret's `host`/`port`/`dbname`/`user`/`password` as
   keyword args (closing P1.1) and add a `connect_timeout=5` (closing
   P0.5 for psycopg2).

2. **Wire OpenAI client timeout.** `SupervisorConfig` already exposes
   `request_timeout_seconds` (default 60s, currently unused). Pass it
   to `OpenAI(api_key=..., timeout=config.request_timeout_seconds)` in
   `_build_llm_default`. Lower the default to **25 seconds** so the
   Lambda's combined work fits inside API Gateway's 30s integration
   timeout.

3. **Document the request budget.** Update `deploy/runbook.md` with the
   "synchronous /ask budget = ~25s" figure and call out that anything
   needing longer answers should switch to an async path (separate
   project — out of scope here).

**Files changed:**
- `src/lina_supervisor/lambda_handler.py`
- `src/lina_supervisor/cli.py`
- `src/lina_supervisor/config.py` (lower default)
- `deploy/runbook.md`
- `tests/unit/lina_supervisor/test_lambda_handler.py` (add a special-char-password test)

**Verification:** unit tests; live smoke test against the sandbox; check
CloudWatch logs for the new "connect_timeout=5" connection events.

---

### Wave 3 — Input limits + stable source IDs (one PR, ~half day)

Two unrelated but small fixes bundled because they both touch
`lambda_handler.py` and the packet schema.

1. **P1.7 — input limits.** Add early-rejection in `lambda_handler`:
   - `len(event.get("body") or "") > MAX_BODY_BYTES` → 413
   - `len(query) > MAX_QUERY_CHARS` → 400
   - `len(history) > MAX_HISTORY_TURNS` → 400
   - per-history-message length and total chars cap → 400
   Defaults from the review (64 KiB body, 4k query, 20 turns, 4k per
   message, 20k total). Each cap configurable via env var. Test the
   four reject paths.

2. **P2.4 — explicit `source_id` on packets.** Add a `source_id: Literal["matters","people","counsel"]`
   field to the base `ResultPacket` in `src/lina_core/packet.py` (or whichever
   module defines it; investigation showed each subsystem subclasses with
   `Literal` overrides). Set the appropriate value in each worker's packet
   construction. On the UI side, `web/src/lib/sources.ts:packetToSource`
   prefers `source_id` when present, falls back to today's heuristic for
   backward compat. Test: each worker's `run()` produces a packet with
   the right `source_id`; UI test (or bundle/import test) imports without
   regression.

**Files changed:**
- `src/lina_supervisor/lambda_handler.py`
- `src/lina_core/packet.py`
- `src/lina_redshift/worker.py`
- `src/lina_users/worker.py`
- `src/lina_vendors/worker.py`
- `web/src/lib/types.ts`
- `web/src/lib/sources.ts`
- `tests/unit/...` for each

**Verification:** unit tests; live curl with an oversized query returns
the right 4xx; UI screenshot shows source cards still rendering.

---

### Wave 4 — Read-only Redshift runtime user (one PR, ~one day)

Closes P0.3.

1. Add a SQL migration `019_create_runtime_user.sql` (idempotent) that
   creates `lina_app_readonly`, grants `USAGE` on the
   `legal_matter_spend` schema, and `SELECT` on the existing tables, the
   one view, and the three MVs. **No** mutate privileges.
2. Add an OpenTofu `aws_secretsmanager_secret` for the runtime user's
   credentials. Set the value out-of-band (operator runs a script after
   `tofu apply`).
3. Update `lambda.tf` so the chat Lambda's env points at the runtime
   secret ARN. Operator workflow stays the same except the migration
   step uses the admin secret and the runtime path uses the new one.
4. Update `lambda_handler.py` to read the runtime secret. Migrations
   are run outside the Lambda anyway (via the `lina-redshift` CLI),
   which keeps using admin creds.
5. Add an integration test: connect as `lina_app_readonly`, attempt
   `INSERT INTO dim_matter`, assert `InsufficientPrivilege`.

**Files changed:**
- `src/lina_redshift/migrations/sql/019_create_runtime_user.sql`
- `infra/tofu/secrets.tf`, `lambda.tf`, `outputs.tf`
- `src/lina_supervisor/lambda_handler.py`
- `deploy/runbook.md`
- `tests/integration/test_redshift_runtime_role.py`

**Verification:** `tofu apply`, run a query end-to-end via curl; check
CloudWatch shows the runtime user; manually attempt an `INSERT` via the
runtime DSN and confirm it fails.

---

### Wave 5 — Build reproducibility + image digests (one PR, ~half day)

Closes P2.1 and P2.2.

1. Replace `deploy/lambda/requirements.txt` with a generated, pinned
   export from `uv.lock`. Add a tiny script
   `deploy/lambda/regen-requirements.sh` that runs
   `uv export --frozen --no-dev --no-emit-project > deploy/lambda/requirements.txt`.
   Add a CI guard that runs the export and fails if the file drifts.
2. Update CI workflow (`ci-integration.yml` or a new `deploy.yml`) so
   that on `main` it builds the image, pushes with the commit SHA as
   tag, and prints the resulting `sha256:...` digest. Operator (or
   tofu) updates the Lambda by digest, not tag. Document the rollback
   recipe ("look up the prior digest in CloudWatch Code History or
   ECR; `aws lambda update-function-code --image-uri <repo>@<digest>`").

**Files changed:**
- `deploy/lambda/Dockerfile`, `requirements.txt`, `regen-requirements.sh`
- `.github/workflows/ci-integration.yml` (or new file)
- `deploy/runbook.md`

**Verification:** local `docker build` from clean cache produces the
same image digest twice; CI run on main pushes a new digest; manual
rollback test against sandbox.

---

### Wave 6 — Secrets out-of-band + doc reconciliation (one PR, ~half day)

Closes P1.8 and P2.3.

1. Remove `aws_secretsmanager_secret_version.openai_api_key` from
   `infra/tofu/secrets.tf`. Keep the `aws_secretsmanager_secret`
   resource. Add a runbook step: "after first apply, run
   `aws secretsmanager put-secret-value --secret-id <arn> --secret-string '{...}'`
   to set/rotate the key."
2. Same treatment for the Redshift runtime user secret added in Wave 4.
3. Sweep `README.md`, `web/README.md`, `deploy/runbook.md`, and
   `infra/tofu/README.md` for stale claims. Cross-check against
   `docs/architecture/data-schema.md` (just added) and the deploy plan.

**Files changed:**
- `infra/tofu/secrets.tf`
- `deploy/runbook.md`, top-level `README.md`, `web/README.md`,
  `infra/tofu/README.md`

**Verification:** fresh-state `tofu apply` does NOT contain the OpenAI
key in `terraform.tfstate` (`grep -F "sk-"` returns nothing); manual
rotate-the-key drill works.

---

### Wave 7 — Smoke test script + alarms (one PR, ~half day)

Bundle the post-deploy automation that the review requested.

1. `scripts/post-deploy-smoke.sh` — runs the seven checks from the
   review (no auth, valid auth, known user lookup, known matter, known
   vendor, oversized query rejection, controlled-failure 500 shape).
2. `infra/tofu/alarms.tf` — CloudWatch alarms for: Lambda errors,
   Lambda duration approaching 25s, API Gateway 5xx, authorizer failure
   rate spike, Redshift connection errors. SNS topic for delivery
   (operator email entered as a tofu variable).

**Files changed:**
- `scripts/post-deploy-smoke.sh`
- `infra/tofu/alarms.tf`, `variables.tf`, `outputs.tf`
- `deploy/runbook.md`

**Verification:** trigger one alarm intentionally (e.g., set Lambda
timeout to 1s and call /ask); confirm the alarm fires and the SNS
topic delivers.

---

## Explicitly deferred

These are real items but they don't fit the stated demo scope:

- **P0.1 (real auth)**: defer until the demo audience needs to expand
  beyond a handful of trusted users. Today the API key + passphrase
  combination is the agreed sandbox posture. Adding Cognito/JWT/BFF is
  a multi-week project.
- **P0.2 (VPC + private subnets, NAT)**: defer for the same reason.
  The current `0.0.0.0/0:5439` rule is gross but contained: the API
  key authorizer gates `/ask`, and Redshift itself only holds sample
  data. Add this when real data lands.
- **P0.4 perfect schemas (one tool per template)**: PR #3's
  prompt-embedded schemas are working live; switching to one tool per
  template is correct and lower-error but not urgent. Reconsider if
  tool-call quality regresses after a model upgrade.
- **P2.5 broad test expansion**: incremental. Each wave above adds
  targeted tests; standalone test-coverage work is hard to scope.

---

## Suggested order in calendar terms

If we work on this part-time:

| Day | Wave |
| --- | --- |
| Day 1 AM | Wave 1 (reliability quick wins) |
| Day 1 PM | Wave 2 (connection lifecycle + timeouts) |
| Day 2 AM | Wave 3 (input limits + source_id) |
| Day 2 PM + Day 3 | Wave 4 (read-only DB user) |
| Day 4 AM | Wave 5 (build reproducibility) |
| Day 4 PM | Wave 6 (secrets + docs) |
| Day 5 AM | Wave 7 (smoke + alarms) |
| Day 5 PM | Live re-test + write a "v1.5 ready" runbook entry |

Total: roughly a calendar week of focused work. Each wave is mergeable
on its own so we can stop at any point if priorities shift.

---

## Open questions to confirm before starting Wave 1

1. **Do you want all 7 waves, or only the items that ship the demo
   forward?** If only the demo, the minimum is Wave 1 + Wave 2 + Wave 3
   (the rest are about graduating beyond demo scope).
2. **For Wave 4 (read-only DB user), do we want to make the existing
   `lina_admin` purely an operator role, or keep it as the migration
   role only?** The plan above does the latter — admin is for migrations
   and seed; runtime is a separate user.
3. **For Wave 5 (image digests), do you want CI to push images
   automatically on `main`, or keep operator-driven `docker push`?** I
   suggested CI; happy to keep manual if you prefer that control.
4. **Is the current "passphrase + browser-shipped API key" auth
   posture explicitly accepted as the sandbox posture, or is part of
   this work to swap that out?** Today's plan defers (P0.1).
