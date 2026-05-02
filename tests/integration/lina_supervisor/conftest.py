"""Fixtures for the supervisor VCR-replayed integration suite.

Two execution modes:

1. **Replay mode** (default): tests run when a recorded YAML cassette exists in
   ``cassettes/<test_name>.yaml``. No ``OPENAI_API_KEY`` is required.
2. **Record mode**: with ``OPENAI_API_KEY`` set and ``--vcr-record=once`` (or
   another VCR record mode), VCR captures real OpenAI API traffic into YAML
   cassettes. The ``Authorization`` and ``OpenAI-Organization`` headers are
   filtered out of recordings before they hit disk.

Tests skip cleanly when neither a cassette nor an API key is present, so the
suite is safe to run on any machine without credentials. See ``README.md`` in
this directory for the recording workflow.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from lina_core.caller import CallerContext
from lina_supervisor.config import SupervisorConfig
from lina_supervisor.graph import build_graph
from lina_supervisor.session import InMemorySessionStore
from lina_supervisor.workers import WorkerHub

CASSETTES_DIR = Path(__file__).parent / "cassettes"


def _cassette_path_for(item: pytest.Item) -> Path:
    """Return the expected cassette path for a test item.

    pytest-vcr stores cassettes at ``<test_module_dir>/cassettes/<test_name>.yaml``
    by default; we mirror that resolution so the skip check is accurate before
    the test ever runs.
    """
    return CASSETTES_DIR / f"{item.name}.yaml"


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    """Skip supervisor integration tests when no cassette and no API key.

    The repo-wide ``tests/conftest.py`` already handles Redshift / OpenSearch
    integration skips. This hook layers on the supervisor-specific rule:
    a cassette OR an API key must exist for each test under this directory.
    """
    has_api_key = bool(os.environ.get("OPENAI_API_KEY"))
    for item in items:
        path = str(item.fspath)
        if "/integration/lina_supervisor/" not in path:
            continue
        if has_api_key:
            continue
        cassette = _cassette_path_for(item)
        if not cassette.exists():
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"no cassette at {cassette.name} and OPENAI_API_KEY "
                        "not set; see tests/integration/lina_supervisor/README.md"
                    )
                )
            )


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, Any]:
    """pytest-vcr configuration: redact secrets from any recorded cassette.

    ``Authorization`` (the OpenAI SDK's default) is stripped before the
    cassette is written. ``OpenAI-Organization`` is filtered defensively in
    case the SDK includes it.
    """
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("openai-organization", "REDACTED"),
            ("x-api-key", "REDACTED"),
        ],
        "decode_compressed_response": True,
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
    }


@pytest.fixture
def openai_client_real() -> Any:
    """Return a real ``openai.OpenAI`` client.

    During replay mode VCR intercepts the underlying HTTP transport, so the
    placeholder API key is never used to authenticate to a live endpoint.
    During record mode, the real ``OPENAI_API_KEY`` is required.
    """
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY", "sk-replay-placeholder")
    return OpenAI(api_key=api_key)


@pytest.fixture
def supervisor_for_test(openai_client_real: Any) -> Iterator[dict[str, Any]]:
    """Compose the supervisor wiring with mocked workers + a real OpenAI client.

    Returns a dict with ``graph``, ``hub``, ``rs_worker``, ``users_worker``,
    ``vendors_worker``, and ``caller`` so tests can configure mock returns
    per-scenario.
    """
    rs_worker = MagicMock(name="redshift_worker")
    users_worker = MagicMock(name="users_worker")
    vendors_worker = MagicMock(name="vendors_worker")
    hub = WorkerHub(
        redshift_worker=rs_worker,
        users_worker=users_worker,
        vendors_worker=vendors_worker,
    )
    config = SupervisorConfig(
        openai_api_key="sk-replay-placeholder",
        max_worker_calls=4,
    )
    session_store = InMemorySessionStore()
    graph = build_graph(
        config=config,
        hub=hub,
        session_store=session_store,
        llm_client=openai_client_real,
    )
    caller = CallerContext(
        user_id="user_jane_smith",
        roles=frozenset({"legal_ops"}),
        request_id="req_supervisor_smoke",
    )
    yield {
        "graph": graph,
        "hub": hub,
        "rs_worker": rs_worker,
        "users_worker": users_worker,
        "vendors_worker": vendors_worker,
        "config": config,
        "caller": caller,
    }
