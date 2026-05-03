# LINA CI Real-Backend Integration Tests (v1.2.0) Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a GitHub Actions workflow that runs the 18 staged integration tests against a dedicated AWS environment (`lina-ci`) on every PR. Authentication via OIDC, IaC for the test backends, S3-backed OpenTofu state.

**Architecture:** Three new IaC modules — `infra/tofu/bootstrap/` (S3 + DynamoDB for state), `infra/tofu/shared/` (OIDC provider + IAM role for GH Actions), `infra/tofu/ci/` (the test backend itself: Redshift Serverless + OpenSearch). One GitHub Actions workflow at `.github/workflows/ci-integration.yml`. State migration from local to S3 for the existing `infra/tofu/` (sandbox) module.

**Spec:** `docs/superpowers/specs/2026-05-03-lina-ci-integration-tests-design.md`. Read §3 file structure, §4 workflow topology, §5 IAM/OIDC, §6 test data lifecycle.

**Authorized minor deviations** (silent): UP035, UP037, RET504, N812 noqa.

**Commit authorship:** Every commit by `koosha <koosha.g@gmail.com>`. **No** AI/Claude attribution. Avoid "OpenAI"/"AI"/"Claude" substrings in commit subjects (commit-message hook blocks them).

**Important constraint:** Subagents do NOT run `tofu apply` against AWS. The plan ships IaC + workflow code; the operator runs `tofu apply` themselves. The exception is `tofu init`, `tofu validate`, `tofu fmt`, and `tofu plan` (read-only AWS calls) which subagents may run if needed for validation.

---

## Task CI-0: Pre-flight (operator-only — not coded)

These four items are operator-driven steps the user does in their AWS console / GitHub repo settings. They are NOT coded in this plan but are required for the IaC + workflow to function. The runbook (Task CI-7) documents them in detail.

- [ ] **Operator: enable GitHub OIDC provider in AWS** — happens automatically on first `tofu apply` of the `shared/` module. No pre-step needed.
- [ ] **Operator: confirm `koosha-cli` IAM user has permissions for `iam:CreateOpenIDConnectProvider`, `iam:CreateRole`, `s3:CreateBucket`, `dynamodb:CreateTable`, `redshift-serverless:*`, `es:*`** — `AdministratorAccess` covers all of these.
- [ ] **Operator: set GitHub branch protection on `main`** to require the `integration-tests / integration` check before merge — done in GitHub UI under Settings → Branches → Branch protection rules.
- [ ] **Operator: confirm AWS Budget alarm at $50/month is in place** — already done in v1.1.0; re-confirm.

---

## Task CI-1: OpenTofu Bootstrap Module (S3 state + DynamoDB lock)

**Files:**
- Create: `infra/tofu/bootstrap/main.tf`
- Create: `infra/tofu/bootstrap/outputs.tf`
- Create: `infra/tofu/bootstrap/.terraform-version`

This module is one-time: create the S3 bucket and DynamoDB table that ALL subsequent OpenTofu modules will use as their remote state backend. Bootstrap state itself stays local (no chicken-and-egg).

- [ ] **Step 1: `main.tf`** — `aws_s3_bucket.tofu_state` (versioning on, encryption with default SSE-S3, block public access true), `aws_dynamodb_table.tofu_locks` (PAY_PER_REQUEST billing, attribute LockID).

- [ ] **Step 2: `outputs.tf`** — bucket_name and table_name outputs so other modules (and humans) can reference them.

- [ ] **Step 3: `.terraform-version`** — `1.11.6`.

- [ ] **Step 4: `tofu init && tofu validate`** in the bootstrap dir.

- [ ] **Step 5: Document in commit message that operator must run `tofu apply` from this dir before any other migration.** Then commit.

  ```bash
  git -C "..." commit -m "infra(ci): add OpenTofu bootstrap module for S3 state and DynamoDB lock"
  ```

---

## Task CI-2: Migrate Existing Sandbox State to S3

**Files:**
- Modify: `infra/tofu/main.tf` (add `backend "s3" {}` block)

This is a state migration, not a resource change. After CI-1 is `tofu apply`'d (operator action), the bucket exists. Adding the backend block to the sandbox module + running `tofu init -migrate-state` carries the local state into S3 without recreating any resources.

- [ ] **Step 1: Add backend block to `infra/tofu/main.tf`:**

  ```hcl
  terraform {
    required_version = ">= 1.11"
    backend "s3" {
      bucket         = "lina-tofu-state-417811547857"
      key            = "sandbox/terraform.tfstate"
      region         = "us-east-1"
      dynamodb_table = "lina-tofu-locks"
      encrypt        = true
    }
    # ... existing required_providers
  }
  ```

  Bucket name pattern: `lina-tofu-state-<account>` — operator confirms via output of CI-1.

- [ ] **Step 2: Document in `infra/tofu/README.md` the migration command:**

  ```bash
  tofu -chdir=infra/tofu init -migrate-state
  ```

  Operator runs this once. Subsequent operators / CI auto-pull from S3.

- [ ] **Step 3: Validate (no apply):**

  ```bash
  tofu -chdir=infra/tofu init -backend=false
  tofu -chdir=infra/tofu validate
  ```

- [ ] **Step 4: Commit.**

  ```bash
  git -C "..." commit -m "infra(sandbox): migrate state backend to S3 with DynamoDB locking"
  ```

---

## Task CI-3: Shared Module — OIDC Provider + IAM Role

**Files:**
- Create: `infra/tofu/shared/main.tf`
- Create: `infra/tofu/shared/oidc.tf`
- Create: `infra/tofu/shared/iam.tf`
- Create: `infra/tofu/shared/outputs.tf`
- Create: `infra/tofu/shared/.terraform-version`

This module owns cross-environment shared resources. For v1.2 it's just the OIDC provider + the `lina-ci-runner` role.

- [ ] **Step 1: `oidc.tf`** — `aws_iam_openid_connect_provider.github` per spec §5.1.

- [ ] **Step 2: `iam.tf`** — `aws_iam_role.ci_runner` with the OIDC trust policy from spec §5.1, plus the resource-scoped permissions enumerated in spec §5.2 (Redshift, Secrets Manager, OpenSearch, CloudWatch, ECR).

- [ ] **Step 3: `outputs.tf`** — `ci_runner_role_arn`.

- [ ] **Step 4: `main.tf`** — provider + S3 backend (key `shared/terraform.tfstate`).

- [ ] **Step 5: `tofu init -backend=false && tofu validate`.**

- [ ] **Step 6: Commit.**

  ```bash
  git -C "..." commit -m "infra(shared): add GitHub OIDC trust and CI runner role"
  ```

---

## Task CI-4: CI Backend Module — Redshift + OpenSearch

**Files:**
- Create: `infra/tofu/ci/main.tf`
- Create: `infra/tofu/ci/redshift.tf`
- Create: `infra/tofu/ci/opensearch.tf`
- Create: `infra/tofu/ci/secrets.tf`
- Create: `infra/tofu/ci/outputs.tf`
- Create: `infra/tofu/ci/.terraform-version`
- Create: `infra/tofu/ci/README.md`

This is structurally a clone of `infra/tofu/`'s Redshift + OpenSearch resources, scoped to a `lina-ci` namespace and tagged `Environment=ci`. Differences from the sandbox module:

- No Lambda or API Gateway (CI doesn't run `lina-chat` against this backend; just unit/integration tests directly).
- No ECR repo (no Lambda image to host).
- Redshift workgroup `lina-ci-wg`, namespace `lina-ci-ns`. OpenSearch domain `lina-ci`.
- Security group ingress `0.0.0.0/0:5439` for the GH Actions runner (which has dynamic IPs); auth via DB password from a CI-specific secret.
- OpenSearch domain access policy allows the `lina-ci-runner` IAM role (referenced via `data.aws_iam_role` from the `shared/` state via remote state data source).

- [ ] **Step 1: `main.tf`** — provider + S3 backend (`key = "ci/terraform.tfstate"`).

- [ ] **Step 2: `redshift.tf`** — namespace `lina-ci-ns` + workgroup `lina-ci-wg` (8 RPU, public, SG with `0.0.0.0/0:5439` and a comment explaining CI-runner IPs are dynamic).

- [ ] **Step 3: `opensearch.tf`** — domain `lina-ci` (t3.small, 1 node, EBS gp3 10 GB).

  Domain access policy: `data "terraform_remote_state" "shared"` to pull the `ci_runner_role_arn`, then a policy statement allowing that ARN `es:ESHttp*` on the domain.

- [ ] **Step 4: `secrets.tf`** — `aws_secretsmanager_secret.redshift_admin` already auto-created by the Redshift Serverless namespace; no need to create one ourselves.

  Add a permission statement (back-edit `infra/tofu/shared/iam.tf`) so `lina-ci-runner` can read `lina-ci-ns`'s admin secret ARN. **Implementation note:** referencing the auto-generated Redshift secret across modules requires either reading it via a `data "aws_secretsmanager_secret"` lookup in the `shared/` module, OR writing the secret ARN as an output of `ci/` and reading it via remote-state in `shared/` via a second apply. Easier: in `shared/iam.tf`, grant `secretsmanager:GetSecretValue` on `arn:aws:secretsmanager:us-east-1:417811547857:secret:redshift!lina-ci-ns-*` (a wildcard ARN that matches the auto-generated name pattern). Document this trade-off in `infra/tofu/ci/README.md`.

- [ ] **Step 5: `outputs.tf`** — `redshift_endpoint`, `redshift_admin_secret_arn`, `opensearch_host`.

- [ ] **Step 6: `infra/tofu/ci/README.md`** — provisioning instructions, cost expectations, tear-down command.

- [ ] **Step 7: `tofu init -backend=false && tofu validate`** in the new dir.

- [ ] **Step 8: Commit.**

  ```bash
  git -C "..." commit -m "infra(ci): add lina-ci Redshift and OpenSearch backends"
  ```

---

## Task CI-5: Helper Scripts for Workflow

**Files:**
- Create: `scripts/ci-redshift-dsn.sh`
- Create: `scripts/ci-opensearch-host.sh`

Tiny shell scripts the workflow calls to fetch live values from AWS. Keeps the workflow YAML readable.

- [ ] **Step 1: `scripts/ci-redshift-dsn.sh`** — pulls workgroup endpoint via `aws redshift-serverless get-workgroup --workgroup-name lina-ci-wg --query 'workgroup.endpoint.address'`, pulls admin password from `redshift!lina-ci-ns-...` secret, URL-encodes the password, prints the DSN. `set -euo pipefail`. Executable.

- [ ] **Step 2: `scripts/ci-opensearch-host.sh`** — pulls domain endpoint via `aws opensearch describe-domain --domain-name lina-ci --query 'DomainStatus.Endpoint'`, prefixes with `https://`, prints. `set -euo pipefail`. Executable.

- [ ] **Step 3: Commit.**

  ```bash
  chmod +x scripts/ci-*.sh
  git -C "..." commit -m "ci(scripts): add helpers for resolving Redshift DSN and OpenSearch host"
  ```

---

## Task CI-6: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/ci-integration.yml`
- Create: `.github/workflows/ci-cost-watcher.yml`

- [ ] **Step 1: `ci-integration.yml`** — exactly the workflow sketched in spec §7. Path filters, OIDC config, uv setup, dsn resolution, seed --reset, integration tests, then a unit-suite sanity check.

  Trigger: `pull_request` on the listed paths + `workflow_dispatch`.

  Concurrency: `integration-${{ github.head_ref || github.ref }}`, `cancel-in-progress: false` (don't kill an in-flight run if a new commit lands; let it finish).

- [ ] **Step 2: `ci-cost-watcher.yml`** — daily cron (UTC 12:00) that uses `aws ce get-cost-and-usage` to check the prior 24h spend on `Environment=ci` tagged resources. If > $5, opens a GitHub issue tagged `cost-anomaly`. Same OIDC pattern, very tiny IAM permissions (`ce:GetCostAndUsage`).

- [ ] **Step 3: Commit.**

  ```bash
  git -C "..." commit -m "ci(workflows): add integration tests and daily cost watcher"
  ```

---

## Task CI-7: Operator Runbook + README

**Files:**
- Create: `deploy/ci-runbook.md`
- Modify: `README.md` (add "CI" section)

- [ ] **Step 1: `deploy/ci-runbook.md`** — 5 sequential operator steps:

  1. `tofu apply` from `infra/tofu/bootstrap/` (creates S3 + DynamoDB)
  2. `tofu init -migrate-state` from `infra/tofu/` (carries sandbox state to S3)
  3. `tofu apply` from `infra/tofu/shared/` (OIDC + IAM role)
  4. `tofu apply` from `infra/tofu/ci/` (Redshift + OpenSearch test backends)
  5. Confirm GitHub branch protection requires the `integration` check

  Document tear-down: `tofu destroy` from `ci/`, then `shared/`, then optionally `bootstrap/` (only if the user wants to dispose of the state buckets — which would lose state for the sandbox too).

- [ ] **Step 2: `README.md`** — add a "CI" section after "Sandbox deployment":

  ```markdown
  ## CI integration tests

  Every PR that touches schema, templates, seed, IaC, or dependencies triggers a
  workflow that runs the integration suite against a dedicated `lina-ci` AWS
  environment. Auth is via GitHub OIDC (no static keys in GitHub Secrets).

  See [`deploy/ci-runbook.md`](./deploy/ci-runbook.md) for first-time operator
  setup. Cost: ~$28/month idle (one shared OpenSearch domain), ~$0.10 per CI
  run. Tear-down: `tofu -chdir=infra/tofu/ci destroy`.
  ```

- [ ] **Step 3: Commit.**

  ```bash
  git -C "..." commit -m "docs(ci): add runbook and top-level README pointer"
  ```

---

## Task CI-8: Final Sweep + Tag

- [ ] **Step 1: Run all gates.**

  ```bash
  uv run pytest -v 2>&1 | tail -3        # all 384 unit tests still pass
  uv run mypy 2>&1 | tail -2
  uv run ruff check src tests 2>&1 | tail -2
  uv run ruff format --check src tests 2>&1 | tail -2
  for d in infra/tofu/bootstrap infra/tofu/shared infra/tofu/ci; do
    bash -c "cd '$PWD/$d' && tofu init -backend=false && tofu validate"
  done
  ```

- [ ] **Step 2: Tag.**

  ```bash
  git -C "..." tag -a v1.2.0 -m "LINA v1.2.0 — real-backend integration tests in CI"
  ```

  No AI/Claude attribution in tag annotation.

- [ ] **Step 3: Operator pushes** (operator-controlled — not subagent).

---

## Self-Review

**Spec coverage:** §3 file structure (CI-1, CI-3, CI-4, CI-5, CI-6, CI-7), §4 topology (CI-6), §5 IAM/OIDC (CI-3), §6 data lifecycle (CI-6 step 1), §7 workflow file (CI-6), §8 cost (operator runbook), §9 state migration (CI-2), §11 success criteria (CI-8).

**Type consistency:** Resource names (`lina-ci-ns`, `lina-ci-wg`, `lina-ci`, `lina-ci-runner`) consistent across IaC modules. Output names (`redshift_endpoint`, `opensearch_host`) consistent with sandbox conventions.

**Placeholder scan:** No "TBD"; every step has actionable code, command, or operator step.

**Constraint:** No subagent runs `tofu apply`, `aws iam create-*`, or any provisioning command. The plan ends with code committed and the v1.2.0 tag created locally; operator triggers all actual AWS provisioning.

---

**Estimated commit count:** 6 (CI-1, CI-2, CI-3, CI-4, CI-5, CI-6, CI-7 — last two combined into one). Plus the tag.
**Estimated wall time:** 2 hours of subagent work, then ~30 min of operator-driven `tofu apply` runs.
**Estimated cost impact:** +~$28/month (the `lina-ci` OpenSearch domain). Existing sandbox cost unchanged.
