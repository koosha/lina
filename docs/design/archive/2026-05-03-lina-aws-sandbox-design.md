# LINA — AWS Sandbox Deployment (v1.1.0) Design

**Status:** Approved for planning
**Date:** 2026-05-03
**Source:** Follow-up to v1.0.0 (Subsystems A + B + C + D) — `lina.md`, `docs/design/2026-05-02-*-design.md`
**Scope:** Provision a demo-grade hosted sandbox of the entire LINA stack on AWS (account `417811547857`, region `us-east-1`). Pre-load existing synthetic seed data so end-to-end demo queries work via a public HTTPS endpoint.

This spec **inherits** all decisions from v1.0.0 design docs. The code itself does not change beyond a thin Lambda handler and an IaC module — no architectural reshaping.

---

## 1. Goal

After this milestone:

- A public HTTPS endpoint (`https://<api-gw-id>.execute-api.us-east-1.amazonaws.com/ask`) accepts `POST` requests with `{user_id, query}` body and a shared API key in the `x-api-key` header.
- Behind that endpoint, `lina-chat ask` runs in AWS Lambda, calls a real Redshift Serverless workgroup and a real OpenSearch domain (both pre-loaded with the existing synthetic seed data), uses Secrets-Manager-stored OpenAI key, and returns a synthesized JSON `SupervisorResponse`.
- The local CLI continues to work unchanged: developers can still `lina-chat repl --user-id user_jane_smith` against the same backends from their laptop using their AWS profile.
- Everything is reproducible from `infra/tofu/` via `tofu apply` and tear-down-able via `tofu destroy`.

**Explicit non-goals:** SSO/Cognito auth, per-user authorization, private-subnet networking, multi-AZ HA, ingestion pipelines from real systems, durable session storage, custom domain / TLS cert. All deferred (see §11).

---

## 2. Architectural Decisions (Locked)

| # | Decision | Choice | Notes |
|---|---|---|---|
| 1 | AWS account / region | Account `417811547857`, region `us-east-1` | Sandbox; single-region |
| 2 | IaC tool | OpenTofu 1.11+ (drop-in Terraform compatible) | HashiCorp's BSL relicense pushed Homebrew core to drop `terraform`; OpenTofu is the FOSS path |
| 3 | IaC layout | `infra/tofu/` in the same repo, S3-backed remote state with DynamoDB locking — **deferred to v1.2**; v1.1 uses local state | Sandbox does not warrant the bootstrap S3+DynamoDB setup yet |
| 4 | Networking | Default VPC + default subnets in `us-east-1`. Redshift Serverless and OpenSearch domain use **public access** with IP allowlist. | Eliminates VPC/NAT cost; sandbox-only |
| 5 | Redshift | Redshift Serverless: namespace `lina-sandbox-ns`, workgroup `lina-sandbox-wg`, base capacity 8 RPU, auto-pause 5 min idle, public access on. Admin user `lina_admin` with password rotated through Secrets Manager. | Cheapest profile; ~$0 idle, ~$0.40/hr active |
| 6 | OpenSearch | One AWS OpenSearch Service domain `lina-sandbox`, version OpenSearch 2.13, instance `t3.small.search` × 1 node, EBS gp3 10 GB, public access endpoint with fine-grained access control disabled (IAM-based). | One domain hosts both `corp_user_profiles_v1` and `vendor_lawyer_profiles_v1` indices |
| 7 | Lambda packaging | Container image (deps exceed 50 MB zip ceiling), ECR-hosted, Python 3.12 | `public.ecr.aws/lambda/python:3.12` base; `uv pip install` of LINA deps; `CMD lina_supervisor.lambda_handler.handler` |
| 8 | Lambda function | `lina-chat-sandbox`, 1024 MB memory, 60 s timeout, env vars wire to Redshift workgroup, OpenSearch domain, Secrets Manager OpenAI key ARN | One-shot `ask` mode only — REPL stays local |
| 9 | API Gateway | HTTP API (cheaper than REST), `POST /ask` route, default `$default` stage, **API key required** via `x-api-key` header | Single shared key for v1.1; can split per-user later |
| 10 | Auth on Redshift | DSN with admin password from Secrets Manager (Lambda fetches at cold start) | IAM auth (`GetClusterCredentials`) deferred to v1.2 |
| 11 | Auth on OpenSearch | AWS SigV4 using Lambda execution role (LINA already supports this via `LINA_OPENSEARCH_AUTH=aws_sigv4`) | Same path used by local dev when configured |
| 12 | OpenAI key storage | Secrets Manager: `lina/sandbox/openai-api-key`. Lambda role grants `secretsmanager:GetSecretValue` on that ARN only. | No env-var key on Lambda; pulled per cold start |
| 13 | Migrations + seed | Run **from operator laptop** post-provision via the existing CLIs (`lina-redshift --target redshift migrate up && seed`, `lina-users indices apply && seed`, `lina-vendors indices apply && seed`). NOT from Lambda. | Lambda is read-only; provisioning is a separate operator action |
| 14 | Sample data | Existing seed: 100 generated matters + 3 named, 600 invoices, ~6k line items, 10 named users + 50 generated, 5 named timekeepers + 200 generated, all UTBMS billing codes | No new fixtures; uses what's in the repo |
| 15 | Observability | Lambda → CloudWatch Logs (1 week retention). API Gateway → CloudWatch access logs. Redshift query logging on. | Bare minimum; no metrics/alerting in v1.1 |
| 16 | Cost guardrail | AWS Budgets alert at $50/month (operator-configured; not in IaC) | Backstop against forgotten domain |
| 17 | Tear-down | `tofu destroy` removes all resources except the AWS account itself. ECR repo, log groups, Secrets Manager secret all marked deletable. | Operator can re-provision on demand |

---

## 3. Repository Additions

```text
lina/
├── infra/
│   └── tofu/                              (NEW)
│       ├── main.tf                        # provider, variables, locals
│       ├── networking.tf                  # data sources for default VPC + subnets
│       ├── redshift.tf                    # namespace + workgroup + admin secret
│       ├── opensearch.tf                  # domain + access policy
│       ├── secrets.tf                     # OpenAI key secret (manual value upload)
│       ├── ecr.tf                         # repository for the Lambda image
│       ├── lambda.tf                      # function + execution role + permissions
│       ├── api_gateway.tf                 # HTTP API + route + key-required + access logs
│       ├── outputs.tf                     # endpoints, ARNs, command snippets
│       ├── README.md                      # bootstrap instructions
│       └── .terraform-version             # pin to 1.11+
├── deploy/
│   ├── lambda/                            (NEW)
│   │   ├── Dockerfile                     # container image based on AWS Lambda Python 3.12
│   │   ├── requirements.txt               # frozen LINA deps for the Lambda image
│   │   └── lambda_handler.py              # entry: handler(event, context) → JSON
│   └── runbook.md                         # post-tofu-apply steps (build/push image, migrate, seed, smoke-test)
└── src/lina_supervisor/
    └── lambda_handler.py                  (NEW — actual handler in the package, imported by deploy/lambda/lambda_handler.py)
```

The deploy directory holds Docker + runbook artifacts. The handler logic itself lives inside the package so it's testable as plain Python.

---

## 4. Lambda Handler

### 4.1 Event shape

API Gateway HTTP API → Lambda payload-format-version 2.0:

```json
{
  "headers": {"x-api-key": "...", "content-type": "application/json"},
  "body": "{\"user_id\": \"user_jane_smith\", \"query\": \"How many open litigation matters?\"}",
  "requestContext": {"http": {"method": "POST", "path": "/ask"}}
}
```

### 4.2 Response shape

```json
{
  "statusCode": 200,
  "headers": {"content-type": "application/json"},
  "body": "<SupervisorResponse JSON>"
}
```

### 4.3 Handler logic

```python
# src/lina_supervisor/lambda_handler.py
import json
import os
from typing import Any

import boto3
from openai import OpenAI

from lina_core.caller import CallerContext
from lina_core.opensearch import OpenSearchConfig, open_client
from lina_supervisor.caller_resolver import CallerResolver
from lina_supervisor.config import SupervisorConfig
from lina_supervisor.graph import build_graph
from lina_supervisor.session import InMemorySessionStore
from lina_supervisor.tools import build_tool_definitions
from lina_supervisor.workers import WorkerHub
from lina_users.worker import UserSearchWorker
from lina_vendors.worker import VendorSearchWorker
from lina_redshift.worker import RedshiftWorker

_secrets_client = boto3.client("secretsmanager")
_OPENAI_KEY_CACHE: dict[str, str] = {}


def _get_openai_key() -> str:
    if "value" not in _OPENAI_KEY_CACHE:
        arn = os.environ["LINA_OPENAI_SECRET_ARN"]
        secret = _secrets_client.get_secret_value(SecretId=arn)
        _OPENAI_KEY_CACHE["value"] = json.loads(secret["SecretString"])["api_key"]
    return _OPENAI_KEY_CACHE["value"]


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    body = json.loads(event.get("body") or "{}")
    user_id = body.get("user_id", "")
    query = body.get("query", "")
    if not user_id or not query:
        return {"statusCode": 400, "body": json.dumps({"error": "user_id and query required"})}

    # Build clients lazily; cache across warm invocations via module globals
    config = SupervisorConfig(
        openai_api_key=_get_openai_key(),
        model=os.environ.get("LINA_SUPERVISOR_MODEL", "gpt-5.2"),
    )
    llm = OpenAI(api_key=config.openai_api_key)
    os_config = OpenSearchConfig(
        host=os.environ["LINA_OPENSEARCH_HOST"],
        auth_mode="aws_sigv4",
        aws_region=os.environ.get("AWS_REGION", "us-east-1"),
    )
    os_client = open_client(os_config)
    rs_worker = RedshiftWorker(connection=_redshift_connection())
    users_worker = UserSearchWorker(client=os_client, config=os_config)
    vendors_worker = VendorSearchWorker(client=os_client, config=os_config)
    hub = WorkerHub(redshift_worker=rs_worker, users_worker=users_worker,
                    vendors_worker=vendors_worker)
    resolver = CallerResolver(users_worker=users_worker)
    caller = resolver.resolve(user_id=user_id, request_id=event.get("requestContext", {})
                              .get("requestId", "lambda-req"))
    graph = build_graph(config=config, hub=hub,
                        session_store=InMemorySessionStore(), llm_client=llm)
    final = graph.invoke({
        "messages": [{"role": "user", "content": query}],
        "caller": caller,
        "worker_call_count": 0,
        "worker_packets": [],
        "truncated": False,
        "answer_text": "",
    })
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps({
            "answer_text": final["answer_text"],
            "worker_call_count": final["worker_call_count"],
            "worker_packets": final["worker_packets"],
            "truncated": final["truncated"],
        }),
    }
```

`_redshift_connection()` reads the Redshift admin password from the same Secrets Manager flow and constructs a `psycopg2` connection.

### 4.4 Cold-start budget

Lambda cold start: ~5–8 s for the container image (~400 MB), dominated by import time of `langgraph` + `langchain-core` + `pydantic`. Acceptable for sandbox; mitigate later via provisioned concurrency if needed.

### 4.5 Memory

1024 MB. Empirically `langgraph` + worker-hub uses ~300 MB at steady state; 1024 gives headroom.

---

## 5. IaC Layout

### 5.1 OpenTofu providers

```hcl
# infra/tofu/main.tf
terraform {
  required_version = ">= 1.11"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.70" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile  # default "lina-sandbox"
  default_tags {
    tags = {
      Project     = "LINA"
      Environment = "sandbox"
      ManagedBy   = "opentofu"
      Owner       = "koosha"
    }
  }
}
```

### 5.2 Variables

```hcl
variable "aws_region"   { default = "us-east-1" }
variable "aws_profile"  { default = "lina-sandbox" }
variable "operator_ip"  { description = "CIDR for IP allowlist (e.g. 73.x.x.x/32)"; default = null }
variable "openai_api_key" { description = "OpenAI key — passed via TF_VAR_openai_api_key env var, not hardcoded"; sensitive = true }
```

### 5.3 Resource summary

| Resource | Name | Notes |
|---|---|---|
| `aws_redshiftserverless_namespace` | `lina-sandbox-ns` | Admin username `lina_admin`; admin_password_secret_kms_key_id default |
| `aws_redshiftserverless_workgroup` | `lina-sandbox-wg` | base_capacity 8, publicly_accessible true, security_group allows operator_ip + Lambda SG |
| `aws_security_group` | `lina-redshift-sg` | Inbound 5439 from operator_ip + Lambda |
| `aws_opensearch_domain` | `lina-sandbox` | t3.small.search × 1, EBS gp3 10 GB, encryption_at_rest, node_to_node_encryption |
| `aws_opensearch_domain_policy` | n/a | Allows operator IAM user `koosha-cli` and Lambda role to use any action on the domain |
| `aws_secretsmanager_secret` | `lina/sandbox/openai-api-key` | JSON string `{"api_key": "..."}`; value uploaded out-of-band |
| `aws_secretsmanager_secret` | `lina/sandbox/redshift-admin` | Created automatically by Redshift Serverless namespace; we just reference its ARN |
| `aws_ecr_repository` | `lina-chat-sandbox` | force_delete true (sandbox tear-down) |
| `aws_iam_role` | `lina-chat-sandbox-execution` | Trust policy: lambda.amazonaws.com. Inline policies: Secrets Manager read on the two secrets, OpenSearch http/* on the domain, CloudWatch Logs |
| `aws_lambda_function` | `lina-chat-sandbox` | package_type IMAGE, image_uri ECR, memory_size 1024, timeout 60 |
| `aws_apigatewayv2_api` | `lina-sandbox-api` | protocol_type HTTP |
| `aws_apigatewayv2_route` | `POST /ask` | authorization_type NONE; api-key check via custom Lambda authorizer **deferred** — initial v1.1 uses an API Gateway usage plan + API key |
| `aws_apigatewayv2_stage` | `$default` | auto_deploy true; access_log_settings → CloudWatch |
| `aws_cloudwatch_log_group` | `/aws/lambda/lina-chat-sandbox` | retention 7 days |
| `aws_cloudwatch_log_group` | `/aws/apigateway/lina-sandbox-api` | retention 7 days |

### 5.4 API key

Important quirk: **API Gateway HTTP APIs do not natively support `x-api-key` validation** the way REST APIs do. Two paths:

- **a)** Switch to API Gateway REST API (more expensive, supports usage plans + API keys natively).
- **b)** Keep HTTP API; implement a tiny Lambda authorizer that compares `x-api-key` to a value in Secrets Manager.

**Choice: (b)** — small extra Lambda (`lina-chat-sandbox-authorizer`, 128 MB, 5 s timeout) reads `lina/sandbox/api-key` from Secrets Manager and returns `isAuthorized: true` if the header matches. Adds ~$0.01/month.

### 5.5 Outputs

```hcl
# infra/tofu/outputs.tf
output "redshift_endpoint" {
  value = aws_redshiftserverless_workgroup.this.endpoint[0].address
}
output "redshift_dsn_template" {
  value = "postgresql://lina_admin:<password>@${aws_redshiftserverless_workgroup.this.endpoint[0].address}:5439/dev"
}
output "opensearch_host" {
  value = "https://${aws_opensearch_domain.this.endpoint}"
}
output "lambda_function_name" { value = aws_lambda_function.this.function_name }
output "api_endpoint" { value = aws_apigatewayv2_api.this.api_endpoint }
output "ecr_repository_url" { value = aws_ecr_repository.this.repository_url }
output "next_steps_runbook" {
  value = "See deploy/runbook.md for image build, migrate, seed, and smoke-test commands."
}
```

---

## 6. Operator Runbook (post-`tofu apply`)

### 6.1 Build + push the Lambda image

```bash
ECR_URL=$(tofu -chdir=infra/tofu output -raw ecr_repository_url)
aws --profile lina-sandbox ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$ECR_URL"
docker build -t "$ECR_URL:v1.1.0" -f deploy/lambda/Dockerfile .
docker push "$ECR_URL:v1.1.0"

# Update Lambda to point at the new image
aws --profile lina-sandbox lambda update-function-code \
  --function-name lina-chat-sandbox \
  --image-uri "$ECR_URL:v1.1.0"
```

### 6.2 Apply migrations + seed against real backends

```bash
# Pull the Redshift admin password Secrets Manager generated when the namespace was created
RS_PASS=$(aws --profile lina-sandbox secretsmanager get-secret-value \
  --secret-id lina/sandbox/redshift-admin --query SecretString --output text \
  | jq -r .password)
RS_HOST=$(tofu -chdir=infra/tofu output -raw redshift_endpoint)

export LINA_REDSHIFT_DSN="postgresql://lina_admin:${RS_PASS}@${RS_HOST}:5439/dev"
.venv/bin/lina-redshift --target redshift migrate up
.venv/bin/lina-redshift --target redshift seed

# OpenSearch — uses your AWS profile via SigV4
export LINA_OPENSEARCH_HOST="$(tofu -chdir=infra/tofu output -raw opensearch_host)"
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1
export AWS_PROFILE=lina-sandbox

.venv/bin/lina-users indices apply
.venv/bin/lina-users seed
.venv/bin/lina-vendors indices apply
.venv/bin/lina-vendors seed
```

Migration apply: ~30 s for Redshift, ~5 s each for OpenSearch.
Seed apply: ~30 s for Redshift (6k line items), ~5 s each for OpenSearch.

### 6.3 Smoke test the public endpoint

```bash
API=$(tofu -chdir=infra/tofu output -raw api_endpoint)
API_KEY=$(aws --profile lina-sandbox secretsmanager get-secret-value \
  --secret-id lina/sandbox/api-key --query SecretString --output text \
  | jq -r .api_key)

curl -X POST "$API/ask" \
  -H "content-type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"user_id": "user_jane_smith",
       "query": "How many open litigation matters do we have?"}' \
  | jq .
```

Expected: a JSON `SupervisorResponse` with `answer_text` containing a count.

### 6.4 Tear-down

```bash
tofu -chdir=infra/tofu destroy
```

Removes everything. ECR repo deletion forces image deletion. CloudWatch log groups deleted with `force_delete`. Secrets Manager secrets deleted with 7-day grace period (recoverable).

---

## 7. Costs (Steady State + Per-Query)

| Component | Idle | Per query | Notes |
|---|---|---|---|
| Redshift Serverless | $0/hr (auto-paused) | ~$0.001/query (8 RPU × <2s active) | Paused after 5 min idle |
| OpenSearch | $0.036/hr × 730 hrs ≈ **$26/month** | $0/query (within 10 GB EBS) | Largest line item |
| Lambda | $0 idle | ~$0.0001/query | 1024 MB × 5 s = ~5,120 GB-ms |
| API Gateway HTTP API | $0 idle | $1/million requests | Trivial |
| Secrets Manager | $0.40/secret-month × 3 = **$1.20/month** | $0.05/10K calls | Trivial |
| CloudWatch Logs | ~$0.50/month at sandbox volume | $0 marginal | 7-day retention caps growth |
| ECR | $0.10/GB-month × ~0.4 GB = **$0.04/month** | $0 | One image |
| OpenAI per query | n/a | ~$0.005–0.05 | gpt-5.2 input + output |
| **Total at idle** | **~$28/month** | | |
| **Total at 1000 queries/month** | **~$30/month** | | OpenAI dominates per-query |

AWS Budget alert at $50/month gives a comfortable margin.

---

## 8. Security Posture (Sandbox-Acceptable, Not Production)

- ✅ TLS in transit (Redshift Serverless and OpenSearch enforce HTTPS)
- ✅ Encryption at rest (KMS default keys for both)
- ✅ OpenAI key in Secrets Manager (Lambda reads via least-privilege IAM)
- ✅ Lambda execution role scoped to specific secret ARNs and one OpenSearch domain
- ⚠️ Redshift / OpenSearch publicly accessible with IP allowlist (acceptable for sandbox; not production)
- ⚠️ Single shared API key (no per-user auth)
- ⚠️ No WAF in front of API Gateway
- ⚠️ No CloudTrail-driven anomaly alerting
- ⚠️ Local OpenTofu state — fine for one operator; needs S3 backend for any team work
- ⚠️ Lambda image pulls from public OpenAI endpoint over the internet — fine for sandbox

All ⚠️ items become "must fix" before any real PII or paid users.

---

## 9. Tear-down Discipline

After a demo session, the operator should either:

- **Pause:** `aws redshift-serverless update-workgroup --workgroup-name lina-sandbox-wg --base-capacity 8` (leave config; Redshift auto-pauses anyway). The OpenSearch domain keeps billing.
- **Tear down:** `tofu destroy`. Everything goes. Cassettes/seed regenerate idempotently on the next `tofu apply` + runbook re-run.

The OpenSearch domain is the only meaningful idle cost; tearing down between demo sessions keeps the bill under $5/month.

---

## 10. Test / Verification

This milestone produces no new automated tests. Verification is **manual**:

1. `tofu apply` succeeds (creates ~22 resources).
2. Image build + push succeeds.
3. Migrations apply against Redshift cleanly (18/18 versions recorded).
4. Seeds load (`mv_matter_spend_summary` has rows).
5. OpenSearch indices created with expected mappings.
6. Smoke `curl` returns a 200 with `answer_text` non-empty.
7. CloudWatch Lambda log shows the worker call(s) the supervisor made.
8. `tofu destroy` removes all resources without manual cleanup.

The integration tests already in the repo (`tests/integration/test_redshift_smoke.py`, `tests/integration/lina_users/`, `tests/integration/lina_vendors/`) **will pass** against the provisioned backends if the operator exports the env vars; this is recommended as a sanity check during the runbook.

---

## 11. Out of Scope (Deferred Follow-ups)

| # | Item | Target milestone |
|---|---|---|
| 1 | S3-backed OpenTofu state + DynamoDB lock | v1.2 |
| 2 | VPC private subnets, NAT gateway, VPC endpoints (Secrets Manager, ECR, API Gateway) | v1.2 |
| 3 | IAM Identity Center / SSO (replace static IAM user keys) | v1.2 |
| 4 | API Gateway custom domain + ACM cert | v1.2 |
| 5 | Cognito user pool for per-user auth | v1.2 |
| 6 | DynamoDB-backed `SessionStore` for multi-process REPL | v1.2 |
| 7 | Provisioned concurrency on Lambda (cold-start mitigation) | v1.2 |
| 8 | Lambda authorizer evolves to JWT validation | v1.2 |
| 9 | Real ingestion pipelines (LEDES → Redshift, Okta → OpenSearch) | v2.0 |
| 10 | CloudWatch metrics, alarms, Slack/PagerDuty wiring | v2.0 |
| 11 | Multi-region failover | v2.0 |
| 12 | WAF in front of API Gateway | v1.2 |

---

## 12. Success Criteria

This milestone is complete when:

- Running `tofu apply` from a fresh checkout produces a working sandbox in ≤ 25 minutes (OpenSearch provisioning is the bottleneck).
- The operator runbook (build/push, migrate, seed, smoke) executes top-to-bottom without manual intervention beyond running the commands.
- A `curl` against the public endpoint returns a sensible answer for "How many open litigation matters do we have?" and "How much did Walker bill on Acme last quarter?"
- `tofu destroy` from a fresh checkout removes 100% of provisioned resources.
- The local CLI (`lina-chat repl`) continues to work against the sandbox backends with the same env vars used by the runbook.
- README has a "Sandbox deployment" section linking to `infra/tofu/README.md` and `deploy/runbook.md`.
- Tagged as `v1.1.0` with annotated message `LINA v1.1.0 — AWS sandbox deployment`.
