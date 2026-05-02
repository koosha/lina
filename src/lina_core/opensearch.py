"""Shared OpenSearch utilities — connection factory + index runner.

Both subsystems A (`lina_users`) and B (`lina_vendors`) consume these helpers
to keep their connection handling and migration semantics identical. Any
divergence belongs in the subsystem package, not here.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass
from pathlib import Path
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


_STATE_INDEX_BODY: dict[str, Any] = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "properties": {
            "applied_at": {"type": "date"},
            "filename": {"type": "keyword"},
        }
    },
}


@dataclass
class IndexRunner:
    """Apply numbered .json mappings in lex order, tracking applied state in a sidecar index.

    `state_index` lets each subsystem keep its own ledger
    (e.g. `lina_users_index_state`, `lina_vendors_index_state`).
    """

    client: Any
    mappings_dir: Path
    state_index: str

    def apply_pending(self) -> list[str]:
        """Apply pending mappings in lex order. Return list of newly applied versions."""
        self._ensure_state_index()
        already = self._already_applied()
        applied: list[str] = []
        for path in sorted(self.mappings_dir.glob("*.json")):
            version = path.stem
            if version in already:
                continue
            self._apply_one(path)
            self.client.index(
                index=self.state_index,
                id=version,
                body={
                    "applied_at": _dt.datetime.now(_dt.UTC).isoformat(),
                    "filename": path.name,
                },
                refresh="wait_for",
            )
            applied.append(version)
        return applied

    def _ensure_state_index(self) -> None:
        if not self.client.indices.exists(index=self.state_index):
            self.client.indices.create(index=self.state_index, body=_STATE_INDEX_BODY)

    def _already_applied(self) -> set[str]:
        result = self.client.search(
            index=self.state_index,
            body={"size": 1000, "query": {"match_all": {}}, "_source": False},
        )
        return {hit["_id"] for hit in result["hits"]["hits"]}

    def _apply_one(self, path: Path) -> None:
        body = json.loads(path.read_text())
        # Index name is filename minus the leading numeric prefix and .json
        # e.g. "001_corp_user_profiles_v1" -> "corp_user_profiles_v1"
        index_name = path.stem.split("_", 1)[1]
        if not self.client.indices.exists(index=index_name):
            self.client.indices.create(index=index_name, body=body)
        else:
            mappings = body.get("mappings")
            if mappings:
                self.client.indices.put_mapping(index=index_name, body=mappings)


def list_pending(*, client: Any, mappings_dir: Path, state_index: str) -> list[str]:
    """Return the list of mapping versions that have not yet been applied."""
    if not client.indices.exists(index=state_index):
        return [p.stem for p in sorted(mappings_dir.glob("*.json"))]
    result = client.search(
        index=state_index,
        body={"size": 1000, "query": {"match_all": {}}, "_source": False},
    )
    already = {hit["_id"] for hit in result["hits"]["hits"]}
    return [p.stem for p in sorted(mappings_dir.glob("*.json")) if p.stem not in already]
