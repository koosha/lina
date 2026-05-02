"""Unit tests for the lina_vendors template registry + DSL surface."""

from __future__ import annotations

import pytest

from lina_vendors.templates import (
    TEMPLATE_REGISTRY,
    all_templates,
    get_template,
)
from lina_vendors.templates.base import APPROVED_INDICES


@pytest.mark.unit
def test_approved_indices_only_holds_vendor_lawyer_profiles_v1() -> None:
    expected = frozenset({"vendor_lawyer_profiles_v1"})
    assert expected == APPROVED_INDICES


@pytest.mark.unit
def test_registry_exposes_four_templates() -> None:
    assert set(TEMPLATE_REGISTRY.keys()) == {
        "timekeeper_lookup",
        "lawyer_search",
        "outside_counsel_filter",
        "practice_area_match",
    }
    assert len(all_templates()) == 4


@pytest.mark.unit
def test_get_template_unknown_raises() -> None:
    from lina_core.errors import UnknownTemplateError

    with pytest.raises(UnknownTemplateError):
        get_template("does_not_exist")


@pytest.mark.unit
def test_every_template_targets_vendor_lawyer_profiles_v1() -> None:
    for tmpl in all_templates():
        assert tmpl.index == "vendor_lawyer_profiles_v1"
