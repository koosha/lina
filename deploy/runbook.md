# LINA Sandbox Operator Runbook

After `tofu apply` from `infra/tofu/` succeeds, follow these steps to make the
sandbox respond to real queries. The `tofu apply` step itself is documented in
[`infra/tofu/README.md`](../infra/tofu/README.md).

All commands assume `aws --profile lina-sandbox` and that the working
directory is the repo root. The local Python virtualenv at `.venv/` is used
for `lina-redshift`, `lina-users`, `lina-vendors` CLIs.

## 1. Build and push the Lambda image

```bash
ECR_URL=$(tofu -chdir=infra/tofu output -raw ecr_repository_url)
aws --profile lina-sandbox ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$ECR_URL"

# Lambda runs x86_64 by default. On Apple Silicon, --platform linux/amd64
# is required so the image's binaries match Lambda's runtime architecture.
docker buildx build --platform linux/amd64 \
  -t "$ECR_URL:v1.1.0" \
  -f deploy/lambda/Dockerfile \
  --push .

# (Or, on x86_64 Linux/macOS, the simpler form works:)
# docker build -t "$ECR_URL:v1.1.0" -f deploy/lambda/Dockerfile .
# docker push "$ECR_URL:v1.1.0"

# Point the Lambda function at the freshly pushed image.
aws --profile lina-sandbox lambda update-function-code \
  --function-name lina-sandbox-chat \
  --image-uri "$ECR_URL:v1.1.0"
```

The Lambda function's OpenTofu resource has `lifecycle.ignore_changes = [image_uri]`
so subsequent `tofu apply` runs do not revert this update.

## 2. Apply migrations and seed against real backends

```bash
RS_PASS=$(aws --profile lina-sandbox secretsmanager get-secret-value \
  --secret-id $(tofu -chdir=infra/tofu output -raw redshift_admin_secret_arn) \
  --query SecretString --output text \
  | jq -r .password)
RS_HOST=$(tofu -chdir=infra/tofu output -raw redshift_endpoint)

export LINA_REDSHIFT_DSN="postgresql://lina_admin:${RS_PASS}@${RS_HOST}:5439/dev"

.venv/bin/lina-redshift --target redshift migrate up
.venv/bin/lina-redshift --target redshift seed
```

```bash
# OpenSearch indices + seed (uses your AWS profile via SigV4)
export LINA_OPENSEARCH_HOST=$(tofu -chdir=infra/tofu output -raw opensearch_host)
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1
export AWS_PROFILE=lina-sandbox

.venv/bin/lina-users indices apply
.venv/bin/lina-users seed
.venv/bin/lina-vendors indices apply
.venv/bin/lina-vendors seed
```

Wall-time guidance:
- Redshift migrations: ~30 s for 18 versions
- Redshift seed: ~30 s for 6k line items
- OpenSearch: ~5 s each per CLI (mappings + bulk seed)

## 3. Smoke test the public endpoint

```bash
API=$(tofu -chdir=infra/tofu output -raw api_endpoint)
API_KEY=$(aws --profile lina-sandbox secretsmanager get-secret-value \
  --secret-id $(tofu -chdir=infra/tofu output -raw api_key_secret_arn) \
  --query SecretString --output text \
  | jq -r .api_key)

curl -X POST "$API/ask" \
  -H "content-type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"user_id": "user_jane_smith",
       "query": "How many open litigation matters do we have?"}' \
  | jq .

curl -X POST "$API/ask" \
  -H "content-type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"user_id": "user_jane_smith",
       "query": "How much did Walker bill on Acme last quarter?"}' \
  | jq .
```

Each response is a JSON envelope with `answer_text`, `worker_call_count`,
`worker_packets`, and `truncated`. A 200 with non-empty `answer_text`
confirms the end-to-end path; a 500 typically means the Lambda image is
absent (run §1 first), the migrations have not been applied (run §2), or
the OpenSearch domain has not finished provisioning (wait ~15 minutes after
the first apply).

The first request is a Lambda cold start (5–8 s). Subsequent requests on
the same warm container are ~1–3 s plus model latency.

## 4. Re-deploying just the Lambda image

When the only change is to LINA's Python code (no IaC changes), skip
`tofu apply` entirely:

```bash
ECR_URL=$(tofu -chdir=infra/tofu output -raw ecr_repository_url)
aws --profile lina-sandbox ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "$ECR_URL"

NEW_TAG=v1.1.$(date -u +%Y%m%d%H%M)
docker buildx build --platform linux/amd64 \
  -t "$ECR_URL:$NEW_TAG" \
  -f deploy/lambda/Dockerfile \
  --push .

aws --profile lina-sandbox lambda update-function-code \
  --function-name lina-sandbox-chat \
  --image-uri "$ECR_URL:$NEW_TAG"
```

## Synchronous /ask request budget

The chat path is synchronous through API Gateway → Lambda → OpenAI →
Redshift/OpenSearch → response. Three timeouts shape the budget:

- **API Gateway integration timeout:** 30 s (hard cap; not configurable
  on HTTP APIs without raising a quota).
- **OpenAI client timeout:** 25 s (default, settable via
  `LINA_SUPERVISOR_REQUEST_TIMEOUT_SECONDS`).
- **Redshift `connect_timeout`:** 5 s (settable via
  `LINA_REDSHIFT_CONNECT_TIMEOUT`); statement timeout 25 s
  (`LINA_STATEMENT_TIMEOUT_MS`).

Total expected per-request budget under normal load: ~25 s. Exceeding
this returns 504 from API Gateway, which the UI surfaces as "Lina
isn't reachable right now." If a use case needs longer answers, switch
to an async or streaming path — don't just bump the Lambda timeout
since API Gateway will still cut off at 30 s.

## 5. Tear-down

```bash
PLUGIN_PROTOCOL_TIMEOUT=300 tofu -chdir=infra/tofu destroy
```

Removes every provisioned resource. Secrets Manager secrets enter a 7-day
recovery window; ECR images and CloudWatch log groups are deleted
immediately. Re-running `tofu apply` recreates everything from scratch and
the runbook above starts fresh.

## Local CLI against the sandbox backends

The same env vars used in §2 also let `lina-chat repl` run from a laptop
against the real backends:

```bash
export OPENAI_API_KEY=sk-proj-...
export LINA_REDSHIFT_DSN="postgresql://lina_admin:${RS_PASS}@${RS_HOST}:5439/dev"
export LINA_OPENSEARCH_HOST=$(tofu -chdir=infra/tofu output -raw opensearch_host)
export LINA_OPENSEARCH_AUTH=aws_sigv4
export LINA_AWS_REGION=us-east-1
export AWS_PROFILE=lina-sandbox

.venv/bin/lina-chat repl --user-id user_jane_smith
```

The local CLI uses your operator IAM user for SigV4 signing on OpenSearch and
the operator's IP allowlist on Redshift, both already provisioned by the IaC.
