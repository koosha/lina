"""End-to-end tests on the populated registry."""

from __future__ import annotations

import pytest

from lina_redshift.errors import UnknownTemplateError
from lina_redshift.templates import TEMPLATE_REGISTRY, all_templates, get_template


@pytest.mark.unit
def test_six_templates_registered() -> None:
    assert set(TEMPLATE_REGISTRY) == {
        "matter_lookup",
        "matter_spend_summary",
        "vendor_spend_summary",
        "timekeeper_rate_analysis",
        "invoice_search",
        "line_item_detail",
    }


@pytest.mark.unit
def test_get_template_returns_instance() -> None:
    t = get_template("matter_lookup")
    assert t.query_type == "matter_lookup"


@pytest.mark.unit
def test_get_template_raises_on_unknown() -> None:
    with pytest.raises(UnknownTemplateError, match="bogus"):
        get_template("bogus")


@pytest.mark.unit
def test_all_templates_have_unique_query_types() -> None:
    types = [t.query_type for t in all_templates()]
    assert len(types) == len(set(types))


@pytest.mark.unit
def test_all_templates_have_non_empty_allowed_roles() -> None:
    for t in all_templates():
        assert t.allowed_roles, f"{t.query_type} has empty allowed_roles"


@pytest.mark.unit
def test_all_templates_have_max_limit_at_least_default() -> None:
    for t in all_templates():
        assert t.max_limit >= t.default_limit


@pytest.mark.unit
def test_all_templates_have_template_version_string() -> None:
    for t in all_templates():
        assert isinstance(t.template_version, str)
        assert len(t.template_version) > 0
