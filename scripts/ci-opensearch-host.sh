#!/usr/bin/env bash
# Resolve the OpenSearch domain endpoint for the lina-ci domain.
#
# Reads:
#   - aws opensearch describe-domain --domain-name lina-ci
# Writes:
#   - https://<endpoint> to stdout
#
# Caller is responsible for exporting AWS credentials (the GH Actions
# configure-aws-credentials step does this for OIDC).

set -euo pipefail

DOMAIN="${LINA_CI_OPENSEARCH_DOMAIN:-lina-ci}"

endpoint=$(aws opensearch describe-domain \
    --domain-name "$DOMAIN" \
    --query 'DomainStatus.Endpoint' \
    --output text)

if [[ -z "$endpoint" || "$endpoint" == "None" ]]; then
    echo "error: could not resolve endpoint for OpenSearch domain $DOMAIN" >&2
    exit 1
fi

printf 'https://%s\n' "$endpoint"
