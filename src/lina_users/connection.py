"""OpenSearch connection factory: basic / aws_sigv4 / none auth modes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlparse

AuthMode = Literal["basic", "aws_sigv4", "none"]


class MissingHostError(RuntimeError):
    """Raised when LINA_OPENSEARCH_HOST is unset."""


@dataclass(frozen=True)
class OpenSearchConfig:
    host: str
    auth_mode: AuthMode
    username: str | None = None
    password: str | None = None
    aws_region: str | None = None
    request_timeout_seconds: int = 30


def resolve_config() -> OpenSearchConfig:
    host = os.environ.get("LINA_OPENSEARCH_HOST")
    if not host:
        raise MissingHostError("LINA_OPENSEARCH_HOST is not set")
    auth_mode_str = os.environ.get("LINA_OPENSEARCH_AUTH", "basic")
    if auth_mode_str not in ("basic", "aws_sigv4", "none"):
        raise ValueError(f"Unknown LINA_OPENSEARCH_AUTH={auth_mode_str!r}")
    auth_mode: AuthMode = auth_mode_str  # type: ignore[assignment]
    timeout_s = int(os.environ.get("LINA_OPENSEARCH_REQUEST_TIMEOUT_SECONDS", "30"))
    return OpenSearchConfig(
        host=host,
        auth_mode=auth_mode,
        username=os.environ.get("LINA_OPENSEARCH_USER"),
        password=os.environ.get("LINA_OPENSEARCH_PASSWORD"),
        aws_region=os.environ.get("LINA_AWS_REGION"),
        request_timeout_seconds=timeout_s,
    )


def open_client(config: OpenSearchConfig) -> Any:
    """Return an `opensearchpy.OpenSearch` client configured per `config`."""
    from opensearchpy import OpenSearch, RequestsHttpConnection

    parsed = urlparse(config.host)
    use_ssl = parsed.scheme == "https"

    if config.auth_mode == "basic":
        if not config.username or not config.password:
            raise ValueError(
                "basic auth requires LINA_OPENSEARCH_USER and LINA_OPENSEARCH_PASSWORD"
            )
        return OpenSearch(
            hosts=[config.host],
            http_auth=(config.username, config.password),
            use_ssl=use_ssl,
            verify_certs=False,
            connection_class=RequestsHttpConnection,
            timeout=config.request_timeout_seconds,
        )
    if config.auth_mode == "aws_sigv4":
        if not config.aws_region:
            raise ValueError("aws_sigv4 auth requires LINA_AWS_REGION")
        import boto3
        from requests_aws4auth import AWS4Auth

        session = boto3.Session()
        creds = session.get_credentials()
        if creds is None:
            raise RuntimeError("no AWS credentials available")
        awsauth = AWS4Auth(
            creds.access_key,
            creds.secret_key,
            config.aws_region,
            "es",
            session_token=creds.token,
        )
        return OpenSearch(
            hosts=[config.host],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=config.request_timeout_seconds,
        )
    return OpenSearch(
        hosts=[config.host],
        use_ssl=use_ssl,
        verify_certs=False,
        timeout=config.request_timeout_seconds,
    )
