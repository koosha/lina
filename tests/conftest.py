"""Shared pytest fixtures for unit and integration suites."""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests when LINA_REDSHIFT_DSN is unset."""
    if os.environ.get("LINA_REDSHIFT_DSN"):
        return
    skip_integration = pytest.mark.skip(reason="LINA_REDSHIFT_DSN not set")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
