#!/usr/bin/env bash
# Regenerate `deploy/lambda/requirements.txt` from `uv.lock`.
#
# Why a generated file rather than `uv export` at Docker build time?
# Vendoring the pinned, hashed list makes the Dockerfile reproducible
# without uv being available in the build context, and lets CI verify
# the file is in sync with the lockfile via a simple `git diff`.
#
# Usage:
#   deploy/lambda/regen-requirements.sh         # regenerate
#   deploy/lambda/regen-requirements.sh --check # exit 1 if regen would change the file

set -euo pipefail

# Resolve repo root so the script works regardless of CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TARGET="$REPO_ROOT/deploy/lambda/requirements.txt"

UV_BIN="${UV_BIN:-uv}"
if ! command -v "$UV_BIN" >/dev/null 2>&1; then
  echo "error: 'uv' not on PATH (set UV_BIN to override)." >&2
  exit 2
fi

CHECK=0
if [[ "${1:-}" == "--check" ]]; then
  CHECK=1
fi

# Use --no-emit-project so the lina-* packages themselves aren't pinned
# (they're copied directly into the image). --no-dev excludes pytest etc.
GEN="$(mktemp)"
trap 'rm -f "$GEN"' EXIT
"$UV_BIN" export \
  --frozen \
  --no-dev \
  --no-emit-project \
  --directory "$REPO_ROOT" \
  > "$GEN"

if [[ "$CHECK" -eq 1 ]]; then
  if ! diff -q "$GEN" "$TARGET" >/dev/null 2>&1; then
    echo "error: $TARGET is out of sync with uv.lock." >&2
    echo "Run: deploy/lambda/regen-requirements.sh" >&2
    diff -u "$TARGET" "$GEN" || true
    exit 1
  fi
  echo "ok: $TARGET matches uv.lock"
  exit 0
fi

mv "$GEN" "$TARGET"
echo "wrote $TARGET ($(wc -l < "$TARGET" | tr -d ' ') lines)"
