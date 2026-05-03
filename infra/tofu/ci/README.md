# LINA CI backends — OpenTofu module

Persistent Redshift Serverless workgroup + OpenSearch domain dedicated to the
GitHub Actions integration test workflow. Tagged `Environment=ci` so cost
reporting can isolate it from the sandbox stack.

## Prerequisites

1. `infra/tofu/bootstrap/` applied (S3 state bucket + DynamoDB lock table).
2. `infra/tofu/shared/` applied (`lina-ci-runner` IAM role exists). The
   OpenSearch domain access policy here references the role ARN via the
   `terraform_remote_state` data source — `tofu plan` against this module
   fails until `shared/` has its first apply.

## Provisioning

```bash
cd infra/tofu/ci

tofu init
PLUGIN_PROTOCOL_TIMEOUT=300 tofu plan
PLUGIN_PROTOCOL_TIMEOUT=300 tofu apply
```

Wall time: ~2 min for Redshift, ~15 min for OpenSearch domain bring-up. Domain
status briefly reports `Processing`; that's expected — wait for `Active`.

## What gets created

| Resource | Notes |
|---|---|
| `aws_redshiftserverless_namespace.this` | `lina-ci-ns`, admin `lina_admin`, password auto-managed in Secrets Manager (`redshift!lina-ci-ns-<rand>`) |
| `aws_redshiftserverless_workgroup.this` | `lina-ci-wg`, base 8 RPU, public, port 5439 |
| `aws_security_group.redshift` | Inbound 5439 from `0.0.0.0/0`. GitHub-hosted runners use rotating IP ranges; auth is enforced by the admin password. |
| `aws_opensearch_domain.this` | `lina-ci`, 2.13, t3.small.search x 1, gp3 10 GB, encrypt-at-rest + node-to-node + enforce-https |
| `aws_opensearch_domain_policy.this` | Grants `lina-ci-runner` (from `shared/` outputs) `es:*` on this domain only |

## Cross-module secret access

The Redshift admin secret is auto-created by AWS with a name pattern
`redshift!lina-ci-ns-<random>`. Rather than reading the ARN across modules,
`infra/tofu/shared/iam.tf` grants `secretsmanager:GetSecretValue` on the
wildcard `arn:aws:secretsmanager:us-east-1:417811547857:secret:redshift!lina-ci-ns-*`.
Trade-off: slightly broader than a single-secret grant, but avoids a circular
remote-state dependency between `shared/` and `ci/`.

## Cost expectation

| Component | Idle | Per CI run |
|---|---|---|
| OpenSearch (t3.small.search) | ~$26/month | ~$0 |
| Redshift Serverless (8 RPU, auto-pause) | ~$0/month | ~$0.10 |
| Secrets Manager (1 auto-managed secret) | ~$0.40/month | n/a |
| CloudWatch logs | ~$1/month | ~$0 |
| **Total at idle** | **~$28/month** | **~$0.10/run** |

Budget alarm at $50/month tied to `Environment=ci` tagged resources. The
`ci-cost-watcher.yml` workflow runs daily and flags any 24h spend > $5.

## Tear-down

```bash
cd infra/tofu/ci
PLUGIN_PROTOCOL_TIMEOUT=300 tofu destroy
```

Removes everything in this module. Sandbox + shared + bootstrap state are
unaffected. Re-applying brings the stack back up cleanly.
