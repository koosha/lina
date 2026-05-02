"""Unit tests for the template AST sanity checker."""

from __future__ import annotations

import pytest

from lina_redshift.templates.base import (
    ALLOWED_FUNCTIONS,
    APPROVED_RELATIONS,
    TemplateValidationError,
    validate_template_sql,
)


@pytest.mark.unit
def test_select_from_approved_relation_passes() -> None:
    sql = "SELECT matter_id FROM vw_matter_current LIMIT :limit"
    validate_template_sql(sql)  # should not raise


@pytest.mark.unit
def test_unapproved_relation_rejected() -> None:
    sql = "SELECT * FROM dim_matter LIMIT :limit"
    with pytest.raises(TemplateValidationError, match="dim_matter"):
        validate_template_sql(sql)


@pytest.mark.unit
@pytest.mark.parametrize("relation", sorted(APPROVED_RELATIONS))
def test_each_approved_relation_passes(relation: str) -> None:
    sql = f"SELECT * FROM {relation} LIMIT :limit"
    validate_template_sql(sql)


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad_sql,expected_substring",
    [
        ("INSERT INTO vw_matter_current VALUES (1)", "INSERT"),
        ("UPDATE vw_matter_current SET matter_id = 'x'", "UPDATE"),
        ("DELETE FROM vw_matter_current WHERE 1=1", "DELETE"),
        ("CREATE TABLE x (id int)", "CREATE"),
        ("DROP TABLE vw_matter_current", "DROP"),
        ("TRUNCATE vw_matter_current", "TRUNCATE"),
        ("UNLOAD ('SELECT 1') TO 's3://x'", "UNLOAD"),
        ("MERGE INTO vw_matter_current USING x", "MERGE"),
    ],
)
def test_non_select_statements_rejected(bad_sql: str, expected_substring: str) -> None:
    with pytest.raises(TemplateValidationError, match=expected_substring):
        validate_template_sql(bad_sql)


@pytest.mark.unit
def test_disallowed_function_rejected() -> None:
    sql = "SELECT pg_sleep(10) FROM vw_matter_current LIMIT :limit"
    with pytest.raises(TemplateValidationError, match="pg_sleep"):
        validate_template_sql(sql)


@pytest.mark.unit
@pytest.mark.parametrize("fn", sorted(ALLOWED_FUNCTIONS))
def test_each_allowed_function_passes(fn: str) -> None:
    sql = f"SELECT {fn}(line_item_total_amount) FROM fact_invoice_line_item LIMIT :limit"
    validate_template_sql(sql)


@pytest.mark.unit
def test_missing_limit_rejected() -> None:
    sql = "SELECT matter_id FROM vw_matter_current"
    with pytest.raises(TemplateValidationError, match="LIMIT"):
        validate_template_sql(sql)


@pytest.mark.unit
def test_join_in_template_rejected() -> None:
    sql = (
        "SELECT v.matter_id, m.matter_name FROM vw_matter_current m "
        "JOIN fact_invoice v ON v.matter_id = m.matter_id LIMIT :limit"
    )
    with pytest.raises(TemplateValidationError, match="join"):
        validate_template_sql(sql)
