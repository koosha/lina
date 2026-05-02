"""Unit tests for the matter_lookup template."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lina_redshift.templates.matter_lookup import (
    MatterLookupParams,
    MatterLookupTemplate,
)


@pytest.fixture
def template() -> MatterLookupTemplate:
    return MatterLookupTemplate()


@pytest.mark.unit
def test_params_accepts_matter_id() -> None:
    p = MatterLookupParams(matter_id="m1")
    assert p.matter_id == "m1"
    assert p.client_matter_id is None


@pytest.mark.unit
def test_params_requires_exactly_one_lookup_field() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        MatterLookupParams()
    with pytest.raises(ValidationError, match="exactly one"):
        MatterLookupParams(matter_id="m1", client_matter_id="CM-1")


@pytest.mark.unit
def test_build_sql_by_matter_id(template: MatterLookupTemplate) -> None:
    params = MatterLookupParams(matter_id="m1")
    sql, binds = template.build_sql(params)
    assert "vw_matter_current" in sql
    assert "matter_id = %(matter_id)s" in sql
    assert binds == {"matter_id": "m1", "limit": template.default_limit}


@pytest.mark.unit
def test_build_sql_by_client_matter_id(template: MatterLookupTemplate) -> None:
    params = MatterLookupParams(client_matter_id="CM-1")
    sql, binds = template.build_sql(params)
    assert "client_matter_id = %(client_matter_id)s" in sql
    assert binds["client_matter_id"] == "CM-1"


@pytest.mark.unit
def test_build_sql_by_owner(template: MatterLookupTemplate) -> None:
    params = MatterLookupParams(matter_owner_user_id="user_jane")
    sql, binds = template.build_sql(params)
    assert "matter_owner_user_id = %(matter_owner_user_id)s" in sql
    assert binds["matter_owner_user_id"] == "user_jane"


@pytest.mark.unit
def test_shape_packet_projects_allowlisted_columns(template: MatterLookupTemplate) -> None:
    rows = [
        {"matter_id": "m1", "matter_name": "X", "secret_field": "leak"},
    ]
    out = template.shape_packet(rows)
    assert out[0]["matter_id"] == "m1"
    assert "secret_field" not in out[0]


@pytest.mark.unit
def test_template_metadata(template: MatterLookupTemplate) -> None:
    assert template.query_type == "matter_lookup"
    assert template.allowed_roles == frozenset({"*"})
    assert template.default_limit > 0
    assert template.max_limit >= template.default_limit
    assert template.template_version
