"""Unit tests for the OpenSearch DSL validator + template registry."""

from __future__ import annotations

import pytest

from lina_users.templates import (
    TEMPLATE_REGISTRY,
    all_templates,
    get_template,
)
from lina_users.templates.base import (
    ALLOWED_TOP_LEVEL_KEYS,
    APPROVED_INDICES,
    FORBIDDEN_QUERY_CLAUSES,
    TemplateValidationError,
    validate_template_query,
)

_ALLOWED = frozenset({"user_id", "display_name", "department"})


@pytest.mark.unit
def test_allowed_top_level_keys_is_locked() -> None:
    expected = frozenset({"query", "size", "from", "sort", "_source", "track_total_hits"})
    assert expected == ALLOWED_TOP_LEVEL_KEYS


@pytest.mark.unit
def test_forbidden_query_clauses_are_locked() -> None:
    assert "script" in FORBIDDEN_QUERY_CLAUSES
    assert "script_score" in FORBIDDEN_QUERY_CLAUSES
    assert "function_score" in FORBIDDEN_QUERY_CLAUSES
    assert "runtime_mappings" in FORBIDDEN_QUERY_CLAUSES


@pytest.mark.unit
def test_approved_indices_only_holds_corp_user_profiles_v1() -> None:
    expected = frozenset({"corp_user_profiles_v1"})
    assert expected == APPROVED_INDICES


@pytest.mark.unit
def test_validator_rejects_aggs_top_level_key() -> None:
    body = {"query": {"match_all": {}}, "aggs": {"x": {"terms": {"field": "user_id"}}}}
    with pytest.raises(TemplateValidationError, match="top-level key 'aggs'"):
        validate_template_query(body, allowed_fields=_ALLOWED, default_size=10, max_size=100)


@pytest.mark.unit
def test_validator_rejects_nested_script() -> None:
    body = {
        "query": {
            "bool": {
                "must": [{"script": {"source": "doc['x'].value > 0"}}],
            }
        }
    }
    with pytest.raises(TemplateValidationError, match="forbidden DSL clause"):
        validate_template_query(body, allowed_fields=_ALLOWED, default_size=10, max_size=100)


@pytest.mark.unit
def test_validator_rejects_source_wildcard() -> None:
    body = {"query": {"match_all": {}}, "_source": ["*"]}
    with pytest.raises(TemplateValidationError, match="wildcard"):
        validate_template_query(body, allowed_fields=_ALLOWED, default_size=10, max_size=100)


@pytest.mark.unit
def test_validator_rejects_unknown_source_field() -> None:
    body = {"query": {"match_all": {}}, "_source": ["password_hash"]}
    with pytest.raises(TemplateValidationError, match="not in allowed_fields"):
        validate_template_query(body, allowed_fields=_ALLOWED, default_size=10, max_size=100)


@pytest.mark.unit
def test_validator_rejects_size_above_max() -> None:
    body = {"query": {"match_all": {}}, "size": 1000}
    with pytest.raises(TemplateValidationError, match="exceeds max_size"):
        validate_template_query(body, allowed_fields=_ALLOWED, default_size=10, max_size=100)


@pytest.mark.unit
def test_validator_accepts_minimal_valid_body() -> None:
    body = {"query": {"match_all": {}}, "size": 10, "_source": ["user_id"]}
    validate_template_query(body, allowed_fields=_ALLOWED, default_size=10, max_size=100)


@pytest.mark.unit
def test_validator_rejects_unknown_sort_field() -> None:
    body = {"query": {"match_all": {}}, "sort": [{"forbidden_field": "asc"}]}
    with pytest.raises(TemplateValidationError, match="sort field 'forbidden_field'"):
        validate_template_query(body, allowed_fields=_ALLOWED, default_size=10, max_size=100)


@pytest.mark.unit
def test_registry_exposes_four_templates() -> None:
    assert set(TEMPLATE_REGISTRY.keys()) == {
        "user_lookup",
        "user_search",
        "manager_chain",
        "people_filter",
    }
    assert len(all_templates()) == 4


@pytest.mark.unit
def test_get_template_unknown_raises() -> None:
    from lina_core.errors import UnknownTemplateError

    with pytest.raises(UnknownTemplateError):
        get_template("does_not_exist")
