#!/usr/bin/env bash
# Pause / resume the entire Lina AWS sandbox between demos.
#
# `down` runs a full `tofu destroy` of the sandbox module. After it
# completes, idle cost is effectively $0 — the only thing left running
# is the shared S3+DynamoDB Tofu backend in the bootstrap module
# (cents/month, shared with future projects).
#
# `up` puts the whole stack back together with one command. It re-runs
# every step that's documented as the post-`tofu apply` operator
# checklist in docs/runbooks/deploy.md:
#   1.  tofu apply                                (~15 min — OpenSearch is the slow one)
#   2.  put OPENAI_API_KEY into Secrets Manager   (prompts if not in env)
#   3.  build + push the Lambda image to ECR      (~3 min)
#   4.  lambda update-function-code               (~30 s)
#   5.  Redshift migrate + seed                   (~1 min)
#   6.  bootstrap the lina_app_readonly user      (~5 s)
#   7.  OpenSearch indices apply + seed (users + vendors)
#   8.  run scripts/post-deploy-smoke.sh against the freshly-stood-up URL
#
# After `up` finishes, the Vercel UI needs a one-time env-var refresh
# (the API Gateway HTTP API gets a new ID on every apply, so the bundle
# embedded with the old VITE_LINA_API_BASE is stale). The script prints
# the exact commands to run.
#
# Usage:
#   ./scripts/sandbox.sh status
#   ./scripts/sandbox.sh down
#   ./scripts/sandbox.sh up
#
# Env:
#   AWS_PROFILE       Default: lina-sandbox
#   AWS_REGION        Default: us-east-1
#   TOFU              Default: tofu (on Apple Silicon use /tmp/tofu)
#   OPENAI_API_KEY    Optional — if unset, `up` prompts for it
#   LINA_IMAGE_TAG    Tag for the chat image (default: v1.6.1)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOFU_DIR="$REPO_ROOT/infra/tofu"
TOFU="${TOFU:-tofu}"
AWS_PROFILE="${AWS_PROFILE:-lina-sandbox}"
REGION="${AWS_REGION:-us-east-1}"
DOMAIN_NAME="${LINA_OPENSEARCH_DOMAIN:-lina-sandbox}"
IMAGE_TAG="${LINA_IMAGE_TAG:-v1.6.1}"
export AWS_PROFILE AWS_REGION="$REGION" AWS_DEFAULT_REGION="$REGION"

usage() {
  cat <<EOF
Lina sandbox pause/resume

  $0 status   Show what's running and the estimated idle cost.
  $0 down     Tear down the entire sandbox via tofu destroy. Idle cost
              after this completes is effectively \$0.
  $0 up       Bring the entire sandbox back online and run the full
              post-apply checklist. Takes ~20 min total.

Env vars:
  AWS_PROFILE       Default: lina-sandbox
  AWS_REGION        Default: us-east-1
  TOFU              Default: tofu (use /tmp/tofu on Apple Silicon)
  OPENAI_API_KEY    Optional — 'up' prompts for it if not set
  LINA_IMAGE_TAG    Tag pushed for the chat container (default: v1.6.1)
EOF
}

_die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

_step() {
  printf '\n\033[1;36m▶ %s\033[0m\n' "$1"
}

# Resolve the operator's public IP for Redshift/OpenSearch allowlisting.
# Tofu's data.http.myip default is api.ipify.org, which has been flaky
# (read-resets mid-handshake during real applies). We try a fallback
# chain and export the result as TF_VAR_operator_ip so tofu doesn't have
# to call out itself. main.tf skips the data source when that var is set.
_resolve_operator_ip() {
  local ip
  for svc in https://checkip.amazonaws.com https://ipv4.icanhazip.com https://api.ipify.org; do
    ip=$(curl -sS --max-time 5 "$svc" 2>/dev/null | tr -d '[:space:]') || continue
    if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      printf '%s/32' "$ip"
      return 0
    fi
  done
  return 1
}

_ensure_operator_ip() {
  if [[ -n "${TF_VAR_operator_ip:-}" ]]; then
    return 0
  fi
  local cidr
  cidr=$(_resolve_operator_ip) \
    || _die "could not resolve public IP from any of checkip.amazonaws.com / icanhazip / ipify. Set TF_VAR_operator_ip manually."
  export TF_VAR_operator_ip="$cidr"
  printf 'Resolved operator IP: %s\n' "$cidr"
}

# Does the sandbox module currently have any resources in state?
_state_count() {
  "$TOFU" -chdir="$TOFU_DIR" state list 2>/dev/null | wc -l | tr -d ' '
}

_tofu_out() {
  "$TOFU" -chdir="$TOFU_DIR" output -raw "$1" 2>/dev/null
}

_get_secret_password() {
  local arn="$1" key="$2"
  aws secretsmanager get-secret-value --secret-id "$arn" \
    --query SecretString --output text \
  | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['$key'])"
}

cmd_status() {
  local n
  n=$(_state_count)
  echo "Sandbox state ($AWS_PROFILE / $REGION):"
  if [[ "$n" == "0" ]]; then
    echo "  Tofu state: empty (sandbox is DOWN)"
    echo
    echo "Idle cost ≈ \$0/mo. Run '$0 up' to bring it back online."
    return 0
  fi
  echo "  Tofu state: $n resources tracked (sandbox is UP)"
  if aws opensearch describe-domain --domain-name "$DOMAIN_NAME" >/dev/null 2>&1; then
    echo "  OpenSearch domain '$DOMAIN_NAME': UP"
  else
    echo "  OpenSearch domain '$DOMAIN_NAME': MISSING (state drift?)"
  fi
  echo
  echo "Idle cost ≈ \$28/mo (OpenSearch dominates). Run '$0 down' to pause to \$0."
}

cmd_down() {
  local n
  n=$(_state_count)
  if [[ "$n" == "0" ]]; then
    echo "Sandbox is already DOWN (tofu state is empty). Nothing to do."
    return 0
  fi
  _ensure_operator_ip
  _step "Tearing down the sandbox via tofu destroy (~5-15 min)…"
  # The 300 s plugin protocol timeout matches the runbook — OpenSearch
  # destroy can spend a while in DELETING state.
  PLUGIN_PROTOCOL_TIMEOUT=300 "$TOFU" -chdir="$TOFU_DIR" destroy -auto-approve
  echo
  echo "Sandbox is DOWN. Idle cost ≈ \$0/mo."
  echo "Run '$0 up' before the next demo (~20 min end-to-end)."
}

cmd_up() {
  _ensure_operator_ip
  # ── 1. tofu apply ──────────────────────────────────────────────────
  _step "1/8 · tofu apply (~15 min — OpenSearch domain bring-up is the slow one)"
  PLUGIN_PROTOCOL_TIMEOUT=300 "$TOFU" -chdir="$TOFU_DIR" apply -auto-approve

  # ── 2. Put OpenAI key into Secrets Manager ─────────────────────────
  _step "2/8 · setting the OpenAI key in Secrets Manager"
  local openai_arn
  openai_arn=$(_tofu_out openai_api_key_secret_arn)
  [[ -n "$openai_arn" ]] || _die "could not read openai_api_key_secret_arn from tofu output"
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    # `read -s` so the key never appears on the terminal.
    read -rsp "  paste OPENAI_API_KEY (sk-...): " OPENAI_API_KEY
    echo
  fi
  [[ -n "${OPENAI_API_KEY:-}" ]] || _die "OPENAI_API_KEY is required"
  aws secretsmanager put-secret-value --secret-id "$openai_arn" \
    --secret-string "$(python3 -c 'import json,os; print(json.dumps({"api_key": os.environ["OPENAI_API_KEY"]}))')" \
    --query 'VersionId' --output text >/dev/null
  unset OPENAI_API_KEY

  # ── 3. Build + push the Lambda image ───────────────────────────────
  _step "3/8 · building + pushing the Lambda image ($IMAGE_TAG, ~3 min)"
  local ecr_url
  ecr_url=$(_tofu_out ecr_repository_url)
  aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "$ecr_url" >/dev/null
  docker buildx build --platform linux/amd64 \
    -t "$ecr_url:$IMAGE_TAG" \
    -f "$REPO_ROOT/deploy/lambda/Dockerfile" \
    --push "$REPO_ROOT"

  # ── 4. Point the Lambda at the new image ───────────────────────────
  _step "4/8 · pointing lina-sandbox-chat at the new image"
  aws lambda update-function-code \
    --function-name lina-sandbox-chat \
    --image-uri "$ecr_url:$IMAGE_TAG" \
    --output text --query 'LastUpdateStatus' >/dev/null
  aws lambda wait function-updated --function-name lina-sandbox-chat
  echo "  Lambda is Active."

  # ── 5. Redshift migrate + seed ─────────────────────────────────────
  _step "5/8 · Redshift migrations + named/bulk seed"
  local rs_admin_arn rs_host rs_pass
  rs_admin_arn=$(_tofu_out redshift_admin_secret_arn)
  rs_host=$(_tofu_out redshift_endpoint)
  rs_pass=$(_get_secret_password "$rs_admin_arn" password)
  export LINA_REDSHIFT_DSN="postgresql://lina_admin:${rs_pass}@${rs_host}:5439/dev"
  uv run --project "$REPO_ROOT" lina-redshift --target redshift migrate up
  uv run --project "$REPO_ROOT" lina-redshift --target redshift seed --reset

  # ── 6. Bootstrap the read-only runtime user ────────────────────────
  _step "6/8 · creating lina_app_readonly + writing its password"
  local runtime_arn
  runtime_arn=$(_tofu_out redshift_runtime_secret_arn)
  uv run --project "$REPO_ROOT" lina-redshift --target redshift \
    bootstrap-runtime-user --put-secret-arn "$runtime_arn"

  # ── 7. OpenSearch indices apply + seed ─────────────────────────────
  _step "7/8 · OpenSearch (users + vendors) indices + seed"
  export LINA_OPENSEARCH_HOST=$(_tofu_out opensearch_host)
  export LINA_OPENSEARCH_AUTH=aws_sigv4
  export LINA_AWS_REGION="$REGION"
  uv run --project "$REPO_ROOT" lina-users indices apply
  uv run --project "$REPO_ROOT" lina-users seed --reset
  uv run --project "$REPO_ROOT" lina-vendors indices apply
  uv run --project "$REPO_ROOT" lina-vendors seed --reset

  # ── 8. Post-deploy smoke test ──────────────────────────────────────
  _step "8/8 · running the post-deploy smoke checks"
  local api_endpoint api_key_arn api_key
  api_endpoint=$(_tofu_out api_endpoint)
  api_key_arn=$(_tofu_out api_key_secret_arn)
  api_key=$(_get_secret_password "$api_key_arn" api_key)
  LINA_API_BASE="$api_endpoint" LINA_API_KEY="$api_key" \
    "$REPO_ROOT/scripts/post-deploy-smoke.sh"

  # ── Done ───────────────────────────────────────────────────────────
  cat <<EOF

────────────────────────────────────────────────────────────────────
  Sandbox is UP. API endpoint: $api_endpoint
────────────────────────────────────────────────────────────────────

The API Gateway HTTP API ID changed during this 'up' run (AWS hands
out a fresh ID on every recreate), so the Vercel UI bundle is now
pointing at the old endpoint. Refresh it once with:

  cd web
  vercel env rm  VITE_LINA_API_BASE production --yes 2>/dev/null
  printf '%s' "$api_endpoint" | vercel env add VITE_LINA_API_BASE production
  vercel --prod --yes

After that finishes, https://lina-web-sooty.vercel.app talks to the
new endpoint again.
EOF
}

case "${1:-status}" in
  status) cmd_status ;;
  down)   cmd_down ;;
  up)     cmd_up ;;
  --help|-h|help) usage ;;
  *)
    printf 'error: unknown command %q\n' "${1:-}" >&2
    usage >&2
    exit 1
    ;;
esac
