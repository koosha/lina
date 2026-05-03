# LINA CI Operator Runbook

First-time setup for the GitHub Actions integration-tests workflow. Five
sequential `tofu apply` steps + one GitHub UI check. Subsequent operators
re-run only the specific module they changed.

All commands assume `aws --profile lina-sandbox` and the repo root as the
working directory. OpenTofu 1.11.6 must be on `PATH`.

> **Apple Silicon note.** If your Homebrew install is at `/usr/local/` (Intel
> Homebrew running under Rosetta on an arm64 Mac), the brew-installed `tofu` is
> x86_64 and the AWS provider plugin will hang at startup with `timeout while
> waiting for plugin to start`. Two workarounds:
>
> 1. Install Apple Silicon Homebrew at `/opt/homebrew/` and reinstall:
>    `arch -arm64 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
>    then `/opt/homebrew/bin/brew install opentofu`.
> 2. Drop a native arm64 binary into your `PATH` ad-hoc:
>    ```bash
>    curl -L https://github.com/opentofu/opentofu/releases/download/v1.11.6/tofu_1.11.6_darwin_arm64.zip -o /tmp/tofu_arm64.zip
>    cd /tmp && unzip -o tofu_arm64.zip && chmod +x tofu
>    # Use /tmp/tofu instead of `tofu` in the commands below
>    ```
>
> Verify with `tofu version` — should report `darwin_arm64`, not `darwin_amd64`.
> If you also already had x86 provider caches, blow them away with
> `find infra/tofu -name .terraform -type d -exec rm -rf {} +` and `rm
> infra/tofu/**/.terraform.lock.hcl` before re-running `tofu init`.

---

## Step 1 — Apply the bootstrap module

Provisions the S3 state bucket and DynamoDB lock table that every other
module uses as its remote backend. Bootstrap state itself stays local.

```bash
tofu -chdir=infra/tofu/bootstrap init
PLUGIN_PROTOCOL_TIMEOUT=300 tofu -chdir=infra/tofu/bootstrap apply
```

Expected output:

```
aws_s3_bucket.tofu_state: Creation complete after ~3s
aws_dynamodb_table.tofu_locks: Creation complete after ~7s

Outputs:
bucket_name = "lina-tofu-state-417811547857"
table_name  = "lina-tofu-locks"
```

Common failures:

- `BucketAlreadyOwnedByYou` — the bucket exists from a prior aborted apply.
  Re-run; OpenTofu imports it on the second pass.
- `BucketAlreadyExists` — the global S3 namespace conflict (vanishingly
  unlikely with the account-id suffix). Change the bucket name in
  `bootstrap/main.tf` and re-apply.

---

## Step 2 — Migrate the sandbox state

The v1.1.0 sandbox stores OpenTofu state locally. Move it into the new S3
bucket. Migration is **non-destructive** — `tofu state push` reads the
existing tfstate and uploads it; no resources are touched.

```bash
tofu -chdir=infra/tofu init -migrate-state
```

OpenTofu prompts:

```
Do you want to copy existing state to the new backend?
  Pre-existing state was found while migrating the previous "local" backend...
  Enter "yes" to copy and "no" to start with an empty state.
```

Type `yes`. Verify with:

```bash
tofu -chdir=infra/tofu state list | wc -l
# Should show ~22 (matches the v1.1.0 resource count).
```

Common failures:

- `AccessDenied: dynamodb:GetItem` — `koosha-cli` lacks DynamoDB perms.
  Confirm the user has `AdministratorAccess` attached.
- `NoSuchBucket` — Step 1 was skipped or failed silently. Re-run Step 1
  first.

---

## Step 3 — Apply the shared module (OIDC + IAM role)

Creates the GitHub OIDC provider in IAM and the `lina-ci-runner` role with
inline policies for Redshift, Secrets Manager, OpenSearch, CloudWatch
Logs, and Cost Explorer.

```bash
tofu -chdir=infra/tofu/shared init
PLUGIN_PROTOCOL_TIMEOUT=300 tofu -chdir=infra/tofu/shared apply
```

Expected output:

```
aws_iam_openid_connect_provider.github: Creation complete
aws_iam_role.ci_runner: Creation complete
aws_iam_role_policy.ci_runner_redshift: Creation complete
aws_iam_role_policy.ci_runner_secrets: Creation complete
aws_iam_role_policy.ci_runner_opensearch: Creation complete
aws_iam_role_policy.ci_runner_logs: Creation complete
aws_iam_role_policy.ci_runner_costexplorer: Creation complete

Outputs:
ci_runner_role_arn       = "arn:aws:iam::417811547857:role/lina-ci-runner"
github_oidc_provider_arn = "arn:aws:iam::417811547857:oidc-provider/token.actions.githubusercontent.com"
```

Common failures:

- `OpenIDConnectProviderAlreadyExistsException` — a previous module
  registered the same provider. Import it:
  `tofu -chdir=infra/tofu/shared import aws_iam_openid_connect_provider.github arn:aws:iam::417811547857:oidc-provider/token.actions.githubusercontent.com`
  then re-apply.

---

## Step 4 — Apply the CI backends

Provisions the `lina-ci` Redshift Serverless workgroup and OpenSearch
domain that the integration tests run against.

```bash
tofu -chdir=infra/tofu/ci init
PLUGIN_PROTOCOL_TIMEOUT=300 tofu -chdir=infra/tofu/ci apply
```

Wall time: ~2 min for Redshift, **~15 min for OpenSearch domain bring-up**.
Domain status briefly reports `Processing` — wait for `Active`.

Expected output:

```
Outputs:
opensearch_host           = "https://search-lina-ci-<hash>.us-east-1.es.amazonaws.com"
redshift_admin_secret_arn = "arn:aws:secretsmanager:us-east-1:417811547857:secret:redshift!lina-ci-ns-<rand>"
redshift_endpoint         = "lina-ci-wg.<account>.us-east-1.redshift-serverless.amazonaws.com"
```

Common failures:

- `terraform_remote_state` cannot read `shared/terraform.tfstate` — Step 3
  was skipped or its apply failed. Confirm
  `aws s3 ls s3://lina-tofu-state-417811547857/shared/` shows a tfstate
  object before retrying.
- OpenSearch stays `Processing` for >20 min — re-check via
  `aws opensearch describe-domain --domain-name lina-ci`. Don't re-run
  apply; it'll transition on its own.

---

## Step 5 — Configure GitHub branch protection

In the GitHub repo (`koosha/lina`):

1. Settings → Branches → Branch protection rules → Add rule for `main`
2. Enable "Require a pull request before merging"
3. Enable "Require status checks to pass before merging"
4. Add `integration-tests / integration` to the required checks list
5. Save

After this, any PR that triggers the workflow must show the green check
before merge.

To verify end-to-end: open a draft PR that modifies
`src/lina_redshift/migrations/sql/`, watch the workflow run, confirm a
green check appears.

---

## Tear-down

Sequential (reverse of bring-up):

```bash
# 1. Tear down the test backends.
PLUGIN_PROTOCOL_TIMEOUT=300 tofu -chdir=infra/tofu/ci destroy

# 2. Optionally drop the OIDC trust + role.
PLUGIN_PROTOCOL_TIMEOUT=300 tofu -chdir=infra/tofu/shared destroy
```

**Do NOT destroy `infra/tofu/bootstrap/`** unless the entire project is
being scrapped. The bootstrap module owns the S3 bucket and DynamoDB table
that hold state for `infra/tofu/` (sandbox), `infra/tofu/shared/`, and
`infra/tofu/ci/`. Destroying it orphans every other module's state.

If you do need to wipe everything, destroy the four modules in the order
`ci → shared → infra/tofu (sandbox) → bootstrap`, then manually empty
the S3 bucket of any remaining state versions before re-running
`tofu destroy` from `bootstrap/`.
