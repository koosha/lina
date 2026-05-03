# LINA AWS Sandbox — OpenTofu module

This module provisions a demo-grade hosted sandbox for LINA on AWS account
`417811547857` in `us-east-1`. The architecture is described in
[`docs/design/2026-05-03-lina-aws-sandbox-design.md`](../../docs/design/2026-05-03-lina-aws-sandbox-design.md).

State is local to whoever runs `tofu apply` (no S3 backend in v1.1). Re-running
from a fresh checkout requires importing or re-creating from scratch.

## Prerequisites

- **AWS profile** `lina-sandbox` configured locally with credentials for IAM
  user `koosha-cli` (admin in this sandbox account). Verify with
  `aws --profile lina-sandbox sts get-caller-identity`.
- **OpenTofu 1.11+** on the PATH. Apple Silicon operators running the x86_64
  build under Rosetta should set `PLUGIN_PROTOCOL_TIMEOUT=300` so the AWS
  provider has time to boot under emulation.
- **Docker** for the post-apply image build step (see `deploy/runbook.md`).
- **AWS Budgets** alert at $50/month (operator-configured outside this module).

## First-time bootstrap

```bash
cd infra/tofu

export TF_VAR_openai_api_key=sk-proj-...

tofu init
PLUGIN_PROTOCOL_TIMEOUT=300 tofu plan
PLUGIN_PROTOCOL_TIMEOUT=300 tofu apply
```

The `apply` step creates ~22 resources. Wall time is dominated by OpenSearch
domain provisioning (~15 minutes); Redshift Serverless namespace + workgroup
take ~2 minutes; the rest are sub-minute.

After `apply` completes, follow `deploy/runbook.md` for the build/push/migrate/
seed/smoke-test sequence — those steps live outside the IaC because they are
per-image-version operator actions.

## What gets created

| Resource | Notes |
|---|---|
| `aws_redshiftserverless_namespace.this` | `lina-sandbox-ns`, admin `lina_admin`, password auto-managed in Secrets Manager |
| `aws_redshiftserverless_workgroup.this` | `lina-sandbox-wg`, base 8 RPU, public, port 5439 |
| `aws_security_group.redshift` | Inbound 5439 from operator IP + Lambda SG |
| `aws_opensearch_domain.this` | `lina-sandbox`, 2.13, t3.small.search × 1, gp3 10 GB |
| `aws_opensearch_domain_policy.this` | Allow operator IAM user + Lambda role + IP-allowlisted reads |
| `aws_secretsmanager_secret.openai_api_key` | `lina/sandbox/openai-api-key` |
| `aws_secretsmanager_secret.api_key` | `lina/sandbox/api-key` (random 40-char alphanumeric) |
| Redshift admin secret | Auto-created by AWS, ARN exposed via output |
| `aws_ecr_repository.this` | `lina-sandbox-chat`, force-delete enabled |
| `aws_iam_role.lambda_exec` | Chat Lambda execution role (Secrets, OpenSearch, Logs) |
| `aws_iam_role.authorizer_exec` | Authorizer Lambda execution role |
| `aws_security_group.lambda` | Egress only |
| `aws_lambda_function.chat` | 1024 MB / 60 s, container image, x86_64 |
| `aws_lambda_function.authorizer` | 128 MB / 5 s, Python 3.12 zip |
| `aws_apigatewayv2_api.this` | HTTP API |
| `aws_apigatewayv2_authorizer.api_key` | REQUEST authorizer, 60 s TTL |
| `aws_apigatewayv2_route.ask` | `POST /ask` |
| `aws_cloudwatch_log_group.*` | Three groups (chat, authorizer, API GW), 7-day retention |

## Cost expectation

| Component | Idle | Per query |
|---|---|---|
| OpenSearch (t3.small.search) | ~$26/month | ~$0 |
| Redshift Serverless (8 RPU) | $0 (auto-pause) | ~$0.001 |
| Lambda + API GW + Logs + ECR + Secrets | ~$2/month | ~$0.0001 |
| OpenAI tokens | n/a | ~$0.005–0.05 |
| **Total at idle** | **~$28/month** | |

OpenSearch is the only meaningful idle cost — `tofu destroy` between demo
sessions drops the bill to ~$0.

## Tear-down

```bash
cd infra/tofu
PLUGIN_PROTOCOL_TIMEOUT=300 tofu destroy
```

Removes everything, including the ECR images (force-delete on the repository),
log groups, and Secrets Manager secrets (7-day recovery window honored).

## Troubleshooting

- **OpenSearch stays in `Processing` for ~15 min after apply** — expected.
  Don't re-run `tofu apply`; the domain transitions to `Active` on its own.
- **Redshift namespace `creating` for ~2 min** — also expected.
- **Lambda invocations 500 right after apply** — the chat Lambda holds the
  ECR image URI but the image hasn't been pushed yet. Run the build/push
  step from `deploy/runbook.md` and the next invocation succeeds.
- **`tofu validate`/`apply` reports `timeout while waiting for plugin to
  start`** — the AWS provider binary is x86_64 only and Rosetta startup
  exceeds OpenTofu's default 60-second plugin timeout. Re-run with
  `PLUGIN_PROTOCOL_TIMEOUT=300` exported.
- **`description doesn't comply with restrictions`** — AWS security-group
  descriptions disallow non-ASCII characters. All bundled descriptions are
  plain ASCII; if you customize them, keep them ASCII.
- **`operator_ip` drift** — when `var.operator_ip` is `null`, the module
  pins to whatever IP the apply machine has at apply-time. Operators on
  roaming connections should set `TF_VAR_operator_ip=<your-cidr>` explicitly.
