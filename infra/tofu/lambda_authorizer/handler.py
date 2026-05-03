"""Tiny API Gateway HTTP API authorizer Lambda.

Validates the ``x-api-key`` header against a Secrets Manager secret. Caches
the secret value across warm invocations so we only pay one read per
container life.
"""

import json
import os

import boto3

_client = boto3.client("secretsmanager")
_CACHE: dict[str, str] = {}


def _load_key() -> str:
    if "key" not in _CACHE:
        arn = os.environ["LINA_API_KEY_SECRET_ARN"]
        secret = _client.get_secret_value(SecretId=arn)
        _CACHE["key"] = json.loads(secret["SecretString"])["api_key"]
    return _CACHE["key"]


def handler(event, _context):
    expected = _load_key()
    headers = event.get("headers") or {}
    provided = headers.get("x-api-key") or headers.get("X-Api-Key") or ""
    return {"isAuthorized": provided == expected}
