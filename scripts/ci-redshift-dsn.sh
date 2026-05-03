#!/usr/bin/env bash
# Resolve the Redshift Serverless DSN for the lina-ci workgroup.
#
# Reads:
#   - workgroup endpoint via aws redshift-serverless get-workgroup
#   - admin password from the auto-managed Redshift secret in Secrets Manager
#     (name pattern: redshift!lina-ci-ns-<random>)
# Writes:
#   - postgresql://lina_admin:<urlencoded>@<host>:5439/dev to stdout
#
# Caller is responsible for exporting AWS credentials (the GH Actions
# configure-aws-credentials step does this for OIDC).

set -euo pipefail

WORKGROUP="${LINA_CI_REDSHIFT_WORKGROUP:-lina-ci-wg}"
NAMESPACE="${LINA_CI_REDSHIFT_NAMESPACE:-lina-ci-ns}"
ADMIN_USER="${LINA_CI_REDSHIFT_ADMIN_USER:-lina_admin}"
DB_NAME="${LINA_CI_REDSHIFT_DB:-dev}"
PORT="${LINA_CI_REDSHIFT_PORT:-5439}"

host=$(aws redshift-serverless get-workgroup \
    --workgroup-name "$WORKGROUP" \
    --query 'workgroup.endpoint.address' \
    --output text)

if [[ -z "$host" || "$host" == "None" ]]; then
    echo "error: could not resolve workgroup endpoint for $WORKGROUP" >&2
    exit 1
fi

secret_arn=$(aws secretsmanager list-secrets \
    --filter "Key=name,Values=redshift!${NAMESPACE}-" \
    --query 'SecretList[0].ARN' \
    --output text)

if [[ -z "$secret_arn" || "$secret_arn" == "None" ]]; then
    echo "error: could not find Redshift admin secret for namespace $NAMESPACE" >&2
    exit 1
fi

password=$(aws secretsmanager get-secret-value \
    --secret-id "$secret_arn" \
    --query 'SecretString' \
    --output text \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["password"])')

encoded_password=$(python3 -c '
import sys
import urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=""))
' "$password")

printf 'postgresql://%s:%s@%s:%s/%s\n' \
    "$ADMIN_USER" "$encoded_password" "$host" "$PORT" "$DB_NAME"
