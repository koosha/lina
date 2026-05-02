"""Unit tests for Claude tool definitions exposed by the supervisor."""

from __future__ import annotations

import pytest

from lina_redshift.templates import TEMPLATE_REGISTRY as RS_REGISTRY
from lina_supervisor.tools import build_tool_definitions, per_template_params_schemas
from lina_users.templates import TEMPLATE_REGISTRY as USERS_REGISTRY
from lina_vendors.templates import TEMPLATE_REGISTRY as VENDORS_REGISTRY


@pytest.mark.unit
def test_three_tools_defined() -> None:
    tools = build_tool_definitions()
    names = [t["name"] for t in tools]
    assert names == ["query_redshift", "search_users", "search_vendors"]


@pytest.mark.unit
def test_each_tool_has_input_schema() -> None:
    tools = build_tool_definitions()
    for tool in tools:
        assert "description" in tool
        assert "input_schema" in tool
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "query_type" in schema["properties"]
        assert "params" in schema["properties"]
        assert set(schema["required"]) == {"query_type", "params"}


@pytest.mark.unit
def test_query_redshift_query_type_enum_matches_redshift_registry() -> None:
    tools = {t["name"]: t for t in build_tool_definitions()}
    enum = set(tools["query_redshift"]["input_schema"]["properties"]["query_type"]["enum"])
    assert enum == set(RS_REGISTRY.keys())


@pytest.mark.unit
def test_search_users_query_type_enum_matches_users_registry() -> None:
    tools = {t["name"]: t for t in build_tool_definitions()}
    enum = set(tools["search_users"]["input_schema"]["properties"]["query_type"]["enum"])
    assert enum == set(USERS_REGISTRY.keys())


@pytest.mark.unit
def test_search_vendors_query_type_enum_matches_vendors_registry() -> None:
    tools = {t["name"]: t for t in build_tool_definitions()}
    enum = set(tools["search_vendors"]["input_schema"]["properties"]["query_type"]["enum"])
    assert enum == set(VENDORS_REGISTRY.keys())


@pytest.mark.unit
def test_build_tool_definitions_per_template_params_schemas() -> None:
    schemas = per_template_params_schemas()
    expected_query_types = (
        set(RS_REGISTRY.keys()) | set(USERS_REGISTRY.keys()) | set(VENDORS_REGISTRY.keys())
    )
    assert set(schemas.keys()) == expected_query_types
    for query_type, schema in schemas.items():
        assert "type" in schema or "$ref" in schema, f"{query_type} schema lacks type/ref"
