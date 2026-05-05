#!/usr/bin/env bash
# Post-deploy smoke test for the Lina sandbox API.
#
# Runs the eight checks called out in docs/plans/2026-05-04-remediation.md
# Wave 7. Exits non-zero on the first failure so it works as a CI gate
# after a Lambda image rotation or an infra apply.
#
# Required env vars:
#   LINA_API_BASE       — e.g. https://kfrbjzy4l7.execute-api.us-east-1.amazonaws.com
#   LINA_API_KEY        — the sandbox API key (Secrets Manager: lina/sandbox/api-key)
#   LINA_DEMO_USER_ID   — defaults to user_jane_smith if unset
#   LINA_DEMO_VENDOR_ID — defaults to vendor_walker if unset
#
# Usage:
#   API_KEY=$(aws secretsmanager get-secret-value ... | jq -r .api_key)
#   LINA_API_BASE=https://... LINA_API_KEY=$API_KEY ./scripts/post-deploy-smoke.sh

set -euo pipefail

: "${LINA_API_BASE:?LINA_API_BASE is required}"
: "${LINA_API_KEY:?LINA_API_KEY is required}"
DEMO_USER="${LINA_DEMO_USER_ID:-user_jane_smith}"
DEMO_VENDOR="${LINA_DEMO_VENDOR_ID:-vendor_walker}"

PASS_COUNT=0
FAIL_COUNT=0

# `_check NAME EXPECTED_STATUS POST_BODY [EXPECT_GREP]`
_check() {
  local name="$1" expected="$2" body="$3" grep_pattern="${4:-}"
  printf "  → %-46s " "$name"

  # Capture status code separately from body. Use --max-time so a hung
  # request fails the check rather than hanging the whole script.
  local response status
  response="$(mktemp)"
  status=$(curl -sS -X POST "$LINA_API_BASE/ask" \
    --max-time 35 \
    -H "content-type: application/json" \
    ${LINA_API_KEY:+-H "x-api-key: $LINA_API_KEY"} \
    -d "$body" \
    -o "$response" \
    -w '%{http_code}' || echo '000')

  if [[ "$status" != "$expected" ]]; then
    printf "FAIL (got %s, expected %s)\n" "$status" "$expected"
    head -c 400 "$response" | sed 's/^/      /' >&2
    rm -f "$response"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 0
  fi

  if [[ -n "$grep_pattern" ]]; then
    if ! grep -q "$grep_pattern" "$response"; then
      printf "FAIL (status %s but body lacked %q)\n" "$status" "$grep_pattern"
      head -c 400 "$response" | sed 's/^/      /' >&2
      rm -f "$response"
      FAIL_COUNT=$((FAIL_COUNT + 1))
      return 0
    fi
  fi

  printf "OK (status %s)\n" "$status"
  PASS_COUNT=$((PASS_COUNT + 1))
  rm -f "$response"
}

# `_check_no_auth NAME EXPECTED_STATUS POST_BODY` — same as _check but
# omits the x-api-key header.
_check_no_auth() {
  local name="$1" expected="$2" body="$3"
  printf "  → %-46s " "$name"
  local response status
  response="$(mktemp)"
  status=$(curl -sS -X POST "$LINA_API_BASE/ask" \
    --max-time 10 \
    -H "content-type: application/json" \
    -d "$body" \
    -o "$response" \
    -w '%{http_code}' || echo '000')
  if [[ "$status" != "$expected" ]]; then
    printf "FAIL (got %s, expected %s)\n" "$status" "$expected"
    head -c 400 "$response" | sed 's/^/      /' >&2
    rm -f "$response"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 0
  fi
  printf "OK (status %s)\n" "$status"
  PASS_COUNT=$((PASS_COUNT + 1))
  rm -f "$response"
}

echo "Smoke-testing $LINA_API_BASE …"

# 1. Missing API key → 401 from authorizer.
_check_no_auth "no auth → 401" "401" \
  '{"user_id":"'"$DEMO_USER"'","query":"hi"}'

# Build payloads via python so we don't have to fight bash's nested quoting
# (apostrophes, parentheses, etc. inside the question strings would all be
# parsed by the shell otherwise).
_payload() {
  python3 -c '
import json, sys
print(json.dumps({"user_id": sys.argv[1], "query": sys.argv[2]}))
' "$@"
}

# 2. Valid auth + simple query → 200 with answer_text.
_check "valid auth + simple query" "200" \
  "$(_payload "$DEMO_USER" "What job title and department does the user with user_id $DEMO_USER have?")" \
  '"answer_text"'

# 3. Known matter lookup → 200 with matter_lookup packet.
_check "known matter lookup" "200" \
  "$(_payload "$DEMO_USER" "Look up matter_acme_v_beta and tell me the name and status.")" \
  'matter_lookup'

# 4. Known vendor / outside counsel search → 200 with counsel data.
_check "known vendor / outside counsel" "200" \
  "$(_payload "$DEMO_USER" "List partners at vendor_id $DEMO_VENDOR with their bar admissions.")" \
  '"answer_text"'

# 5. Oversized query → 400 with the explicit cap message.
big_q=$(python3 -c 'print("x"*5000)')
_check "oversized query (>4000 chars)" "400" \
  "$(_payload "$DEMO_USER" "$big_q")" \
  'exceeds 4000'

# 6. History over turn cap → 400.
big_history=$(python3 -c '
import json, sys
print(json.dumps({
    "user_id": sys.argv[1],
    "query": "hi",
    "history": [{"role": "user", "content": "x"}] * 25,
}))
' "$DEMO_USER")
_check "history > MAX_HISTORY_TURNS" "400" \
  "$big_history" \
  'history exceeds'

# 7. Body bigger than the cap → 413.
big_body=$(python3 -c '
import json
print(json.dumps({"user_id": "u", "query": "hi", "filler": "x"*70000}))
')
_check "request body > LINA_MAX_BODY_BYTES" "413" \
  "$big_body" \
  'too large'

# 8. Missing query field → 400 (the lambda's input-validation path).
missing_query=$(python3 -c '
import json, sys
print(json.dumps({"user_id": sys.argv[1]}))
' "$DEMO_USER")
_check "missing query field" "400" \
  "$missing_query" \
  '"query is required"'

echo
printf "%d passed, %d failed.\n" "$PASS_COUNT" "$FAIL_COUNT"
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
