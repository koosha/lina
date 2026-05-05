# LINA AWS Sandbox Deployment (v1.1.0) Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Provision a demo-grade hosted sandbox of LINA on AWS (account `417811547857`, region `us-east-1`) using OpenTofu. Pre-load existing seed data. Expose `lina-chat ask` via a public HTTPS endpoint guarded by an API key.

**Architecture:** OpenTofu module under `infra/tofu/` provisions Redshift Serverless + OpenSearch + Lambda (container image) + API Gateway HTTP API + Secrets Manager + ECR. Lambda handler in `src/lina_supervisor/lambda_handler.py` (testable as plain Python) wrapped by a thin entry at `deploy/lambda/lambda_handler.py` for AWS. A small authorizer Lambda validates `x-api-key` against Secrets Manager. Operator runbook documents post-`tofu apply` build/push/migrate/seed/smoke steps.

**Tech Stack:** OpenTofu 1.11+, AWS provider 5.70+, Python 3.12 in Lambda container, boto3, openai, langgraph (already in the repo).

**Spec:** `docs/design/2026-05-03-lina-aws-sandbox-design.md`. Read §3 file structure, §4 handler logic, §5 IaC layout, §6 runbook before each task.

**Authorized minor deviations** (silent):
- UP035, UP037, RET504, N812 noqa, `result.stdout` for Click

**Commit authorship:** Every commit authored by `koosha <koosha.g@gmail.com>`. **No** AI/Claude attribution.

**Important constraint:** This plan does NOT include `tofu apply`. The plan ships the IaC + Lambda code + runbook; the operator runs `tofu apply` themselves so AWS resources are only created with their explicit consent. Subagents should never run AWS provisioning commands.

---

## Task S1: Lambda Handler (Pure Python, Testable Locally)

**Files:**
- Create: `src/lina_supervisor/lambda_handler.py`
- Create: `tests/unit/lina_supervisor/test_lambda_handler.py`

The handler is part of the package so unit tests can import it. The deploy-time entry shim in `deploy/lambda/lambda_handler.py` will simply re-export `handler`.

- [ ] **Step 1: Failing tests** — 6 tests using `MagicMock` for the entire AWS surface:
  - `test_handler_rejects_missing_user_id_with_400`
  - `test_handler_rejects_missing_query_with_400`
  - `test_handler_returns_200_with_answer_for_valid_request` (uses mocked LLM client + mocked workers)
  - `test_handler_caches_openai_key_across_warm_invocations` (asserts `secretsmanager.get_secret_value` called once across two handler invocations)
  - `test_handler_response_includes_worker_packets_and_call_count`
  - `test_handler_translates_handler_exception_to_500_with_error_envelope`

- [ ] **Step 2: Implement `lambda_handler.py`** per spec §4.3. Module-level globals cache the OpenAI key and (warm Lambda) the worker hub. Handler:
  1. Parses `event["body"]` JSON (or returns 400)
  2. Builds `SupervisorConfig` with key from cached secret
  3. Builds `WorkerHub` with real `RedshiftWorker`, `UserSearchWorker`, `VendorSearchWorker`
  4. Resolves caller via `CallerResolver`
  5. Compiles graph, invokes
  6. Returns API-Gateway-shaped 200 with JSON body
  7. Catches uncaught exceptions, logs via structlog, returns 500 with `{"error": str(exc)}` body

  Make the worker-construction helper functions injectable so unit tests can substitute mocks. For example:

  ```python
  def handler(event, context, *, _build_workers=_build_workers_default,
              _build_llm=_build_llm_default):
      ...
  ```

- [ ] **Step 3: Run tests, mypy, ruff. Commit.**
  ```bash
  git -C "..." add src/lina_supervisor/lambda_handler.py tests/unit/lina_supervisor/test_lambda_handler.py
  git -C "..." commit -m "feat(supervisor): add Lambda handler module with cached secrets"
  ```

---

## Task S2: Lambda Container Image

**Files:**
- Create: `deploy/lambda/Dockerfile`
- Create: `deploy/lambda/requirements.txt`
- Create: `deploy/lambda/lambda_handler.py` (thin re-export)

- [ ] **Step 1: Write `Dockerfile`** based on `public.ecr.aws/lambda/python:3.12`:

  ```dockerfile
  FROM public.ecr.aws/lambda/python:3.12

  # Install system deps (psycopg2 needs libpq)
  RUN dnf install -y postgresql-libs && dnf clean all

  # Copy and install Python deps
  COPY deploy/lambda/requirements.txt /tmp/requirements.txt
  RUN pip install --no-cache-dir -r /tmp/requirements.txt

  # Copy LINA source
  COPY src/ ${LAMBDA_TASK_ROOT}/

  # Copy the entry point
  COPY deploy/lambda/lambda_handler.py ${LAMBDA_TASK_ROOT}/lambda_handler.py

  CMD ["lambda_handler.handler"]
  ```

- [ ] **Step 2: Generate `requirements.txt`** by exporting the project's runtime deps:

  ```bash
  .venv/bin/pip install pip-tools  # if not present
  .venv/bin/pip-compile pyproject.toml \
      --output-file deploy/lambda/requirements.txt \
      --no-header --no-annotate
  # Strip dev-only deps; keep: psycopg2-binary, pydantic, sqlglot, python-ulid,
  # structlog, click, Faker, opensearch-py, requests-aws4auth, openai, langgraph,
  # langchain-core, langchain-openai, boto3
  ```

  If `pip-compile` produces too much, hand-write a minimal `requirements.txt` with just the package names + version pins from the venv:

  ```
  boto3>=1.34
  click>=8.1
  Faker>=24.0
  langchain-core>=0.3
  langchain-openai>=0.2
  langgraph>=0.2
  openai>=1.50
  opensearch-py>=2.7
  psycopg2-binary>=2.9.9
  pydantic>=2.6
  python-ulid>=2.2
  requests-aws4auth>=1.2
  sqlglot>=23.0
  structlog>=24.1
  ```

- [ ] **Step 3: Write `deploy/lambda/lambda_handler.py`** as a one-line re-export so the Lambda container's `CMD` resolves to the package handler:

  ```python
  """Lambda entry shim. Re-exports the handler from the lina_supervisor package."""
  from lina_supervisor.lambda_handler import handler

  __all__ = ["handler"]
  ```

- [ ] **Step 4: Verify image builds locally** (Docker required — the runbook will note this):

  ```bash
  docker build -t lina-chat-sandbox:test -f deploy/lambda/Dockerfile .
  docker images lina-chat-sandbox:test
  ```

  Should produce an image around 400 MB. Don't push anywhere; this is just the build verification.

- [ ] **Step 5: Commit.**
  ```bash
  git -C "..." add deploy/lambda
  git -C "..." commit -m "feat(deploy): add Lambda container image and requirements pin"
  ```

---

## Task S3: OpenTofu Module — Networking + Redshift + OpenSearch

**Files:**
- Create: `infra/tofu/main.tf`
- Create: `infra/tofu/variables.tf`
- Create: `infra/tofu/networking.tf`
- Create: `infra/tofu/redshift.tf`
- Create: `infra/tofu/opensearch.tf`
- Create: `infra/tofu/.terraform-version`

- [ ] **Step 1: `main.tf`** — `terraform` block, AWS provider with default tags (per spec §5.1)

- [ ] **Step 2: `variables.tf`** — `aws_region`, `aws_profile`, `operator_ip` (CIDR like `73.x.x.x/32` — null means "compute from current `myip` data source"; document that operators should set it explicitly for stability), `openai_api_key` (sensitive, passed via `TF_VAR_openai_api_key`).

  Use a `data "http" "myip" { url = "https://api.ipify.org" }` to compute current public IP if `operator_ip` is null:

  ```hcl
  locals {
    operator_cidr = var.operator_ip != null ? var.operator_ip : "${chomp(data.http.myip.response_body)}/32"
  }
  ```

- [ ] **Step 3: `networking.tf`** — data sources for default VPC + default subnets:

  ```hcl
  data "aws_vpc" "default" { default = true }
  data "aws_subnets" "default" {
    filter { name = "vpc-id"; values = [data.aws_vpc.default.id] }
  }
  ```

  Plus a security group `lina-redshift-sg` allowing inbound 5439 from `local.operator_cidr` and from the Lambda function's security group (created in Task S5).

- [ ] **Step 4: `redshift.tf`** —
  - `aws_redshiftserverless_namespace.this` — name `lina-sandbox-ns`, admin username `lina_admin`, `manage_admin_password = true` (Redshift auto-creates a Secrets Manager secret)
  - `aws_redshiftserverless_workgroup.this` — name `lina-sandbox-wg`, namespace = above, base_capacity 8, publicly_accessible true, security_group_ids = [`lina-redshift-sg`], subnet_ids = data.aws_subnets.default.ids

- [ ] **Step 5: `opensearch.tf`** —
  - `aws_opensearch_domain.this` with domain_name `lina-sandbox`, engine_version `OpenSearch_2.13`, cluster_config { instance_type t3.small.search, instance_count 1, dedicated_master_enabled false }, ebs_options { enabled true, volume_size 10, volume_type gp3 }, encrypt_at_rest enabled, node_to_node_encryption enabled, domain_endpoint_options { enforce_https = true }
  - `aws_opensearch_domain_policy` with statements allowing principal arn `arn:aws:iam::417811547857:user/koosha-cli` (operator) and the Lambda execution role ARN (created in Task S5; reference via `aws_iam_role.lambda_exec.arn`) on `es:*` for the domain ARN

- [ ] **Step 6: `.terraform-version`** — single line `1.11.6` (matches OpenTofu install).

- [ ] **Step 7: `tofu init && tofu validate` locally.** Don't run `tofu plan` or `apply` — those need real AWS.

- [ ] **Step 8: Commit.**
  ```bash
  git -C "..." add infra/tofu
  git -C "..." commit -m "infra(sandbox): add Redshift Serverless and OpenSearch modules"
  ```

---

## Task S4: OpenTofu Module — Secrets + ECR + Lambda + API Gateway

**Files:**
- Create: `infra/tofu/secrets.tf`
- Create: `infra/tofu/ecr.tf`
- Create: `infra/tofu/lambda.tf`
- Create: `infra/tofu/api_gateway.tf`
- Create: `infra/tofu/outputs.tf`

- [ ] **Step 1: `secrets.tf`** —
  - `aws_secretsmanager_secret.openai_api_key` (name `lina/sandbox/openai-api-key`, recovery_window_in_days 7) + `aws_secretsmanager_secret_version` with `secret_string = jsonencode({ api_key = var.openai_api_key })`
  - `aws_secretsmanager_secret.api_key` (name `lina/sandbox/api-key`) — value generated via `random_password.api_key` (32 chars, alphanumeric)

- [ ] **Step 2: `ecr.tf`** — `aws_ecr_repository.this` with name `lina-chat-sandbox`, force_delete true, image_scanning_configuration { scan_on_push = true }

- [ ] **Step 3: `lambda.tf`** —
  - `aws_iam_role.lambda_exec` with trust policy for `lambda.amazonaws.com`. Inline policies:
    - `AWSLambdaBasicExecutionRole` (managed)
    - Custom policy: `secretsmanager:GetSecretValue` on the two secret ARNs + the auto-created Redshift admin secret (`aws_redshiftserverless_namespace.this.namespace.admin_password_secret_arn`)
    - Custom policy: `es:ESHttp*` on the OpenSearch domain ARN
  - `aws_lambda_function.chat` with package_type IMAGE, image_uri = `${aws_ecr_repository.this.repository_url}:v1.1.0` (operator pushes this tag in the runbook), memory_size 1024, timeout 60, env vars: `LINA_OPENSEARCH_HOST`, `LINA_OPENSEARCH_AUTH=aws_sigv4`, `LINA_OPENAI_SECRET_ARN`, `LINA_REDSHIFT_SECRET_ARN`, `LINA_REDSHIFT_HOST`, `LINA_SUPERVISOR_MODEL=gpt-5.2`, `LINA_LOG_FORMAT=json`. Lifecycle ignore_changes on `image_uri` so subsequent `aws lambda update-function-code` calls don't drift the state.
  - `aws_security_group.lambda` allowing egress to anywhere (default), no ingress.
  - Lambda VPC config — **omitted** for sandbox (Lambda runs in AWS-managed network; can still call Redshift Serverless public endpoint and OpenSearch public endpoint).
  - `aws_lambda_function.authorizer` — second tiny Lambda, package_type Zip, runtime python3.12, memory 128, timeout 5. Inline source via `archive_file` data source: reads `lina/sandbox/api-key` from Secrets Manager, returns `{"isAuthorized": event.headers["x-api-key"] == cached_key}`.
  - `aws_cloudwatch_log_group.lambda_chat` and `aws_cloudwatch_log_group.lambda_authorizer` with retention_in_days 7

- [ ] **Step 4: `api_gateway.tf`** —
  - `aws_apigatewayv2_api.this` protocol_type HTTP, name `lina-sandbox-api`
  - `aws_apigatewayv2_stage.default` name `$default`, auto_deploy true, access_log_settings → CloudWatch log group
  - `aws_cloudwatch_log_group.api_gateway` retention 7 days
  - `aws_apigatewayv2_authorizer.api_key` type REQUEST, authorizer_uri = lambda authorizer's invoke ARN, identity_sources = `["$request.header.x-api-key"]`, authorizer_payload_format_version "2.0", enable_simple_responses true, authorizer_result_ttl_in_seconds 60
  - `aws_apigatewayv2_integration.chat` integration_type AWS_PROXY, integration_uri = chat Lambda's invoke ARN, payload_format_version "2.0"
  - `aws_apigatewayv2_route.ask` route_key `POST /ask`, target = `integrations/${aws_apigatewayv2_integration.chat.id}`, authorizer_id = api_key authorizer, authorization_type CUSTOM
  - `aws_lambda_permission.allow_api_gw_chat` and `aws_lambda_permission.allow_api_gw_authorizer` with source_arn referencing the API

- [ ] **Step 5: `outputs.tf`** — per spec §5.5

- [ ] **Step 6: `tofu init && tofu validate`.**

- [ ] **Step 7: Commit.**
  ```bash
  git -C "..." add infra/tofu
  git -C "..." commit -m "infra(sandbox): add Lambda, API Gateway, ECR, Secrets Manager"
  ```

---

## Task S5: Operator Runbook + IaC README

**Files:**
- Create: `infra/tofu/README.md`
- Create: `deploy/runbook.md`
- Modify: `README.md` (add a "Sandbox deployment" section)

- [ ] **Step 1: `infra/tofu/README.md`** — covers:
  - Prerequisites (`aws --profile lina-sandbox`, `tofu` 1.11+, Docker, the operator's $50 budget alert)
  - First-time bootstrap:
    ```bash
    cd infra/tofu
    export TF_VAR_openai_api_key=sk-proj-...
    tofu init
    tofu plan
    tofu apply
    ```
  - What gets created (resource summary table)
  - Cost expectation
  - Tear-down: `tofu destroy`
  - Troubleshooting: OpenSearch "in-use" status (~15 min provision); Redshift namespace "creating" (~2 min); Lambda image not yet pushed (Lambda function will exist but invocations 500 — push image then retry)

- [ ] **Step 2: `deploy/runbook.md`** — exactly the commands from spec §6, plus:
  - The `docker buildx` invocation for cross-arch builds if operator is on Apple Silicon (Lambda runs x86_64 by default; Dockerfile must specify `--platform linux/amd64`)
  - Smoke-test cURL commands for both seed queries: "How many open litigation matters do we have?" and "How much did Walker bill on Acme last quarter?"
  - Re-deploying just the Lambda image (without `tofu apply`)

- [ ] **Step 3: Update top-level `README.md`** — add a section after "Quality gates":

  ```markdown
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
  ```

- [ ] **Step 4: Commit.**
  ```bash
  git -C "..." add infra/tofu/README.md deploy/runbook.md README.md
  git -C "..." commit -m "docs(sandbox): add OpenTofu README, deploy runbook, and top-level pointer"
  ```

---

## Task S6: Final Sweep + Tag

**Files:** none (just gates + tag)

- [ ] **Step 1: Run all gates.**
  ```bash
  .venv/bin/pytest -v 2>&1 | tail -3
  .venv/bin/mypy
  .venv/bin/ruff check src tests
  .venv/bin/ruff format --check src tests
  ```
  Expected: 378+ unit tests still passing (Lambda handler tests bring the count up by ~6); mypy clean; ruff clean.

- [ ] **Step 2: Run `tofu validate` one final time** to ensure no IaC drift slipped into the commits.
  ```bash
  ( cd infra/tofu && tofu validate )
  ```

- [ ] **Step 3: Commit any stragglers, then tag.**
  ```bash
  git -C "..." tag -a v1.1.0 -m "LINA v1.1.0 — AWS sandbox deployment"
  ```
  Tag annotation must have **no AI/Claude attribution**.

- [ ] **Step 4: Push (when operator is ready).**
  Don't push from the subagent; final push to remote is the operator's call.

---

## Self-Review

**Spec coverage:** §3 file structure (S1–S5), §4 handler (S1, S2), §5 IaC (S3, S4), §6 runbook (S5), §10 verification (operator-driven, runbook step), §11 out of scope (documented in spec, not built).

**Type consistency:** Lambda handler imports `RedshiftWorker`, `UserSearchWorker`, `VendorSearchWorker`, `WorkerHub`, `CallerResolver`, `SupervisorConfig`, `build_graph`, `OpenSearchConfig`, `open_client`, `InMemorySessionStore` — all already exist in the codebase with stable signatures. No new types introduced.

**Placeholder scan:** No "TBD"; every step has actionable commands or code.

**Constraint:** No subagent runs `tofu apply`, `aws lambda invoke`, `aws cloudformation`, `aws ec2`, `aws redshift-serverless create-*`, `docker push`, or any other command that creates billable AWS resources. The plan ends with code committed and a tag created locally; the operator triggers the actual provisioning.

---

**Estimated commit count:** 6 (one per task).
**Estimated test count delta:** +6 unit tests in Lambda handler.
**Estimated wall time:** 2–3 hours of subagent work.
