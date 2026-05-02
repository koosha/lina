"""Unit tests for timekeeper_lookup template."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lina_vendors.templates.timekeeper_lookup import (
    TimekeeperLookupParams,
    TimekeeperLookupTemplate,
)


@pytest.mark.unit
def test_timekeeper_lookup_requires_exactly_one_selector() -> None:
    with pytest.raises(ValidationError):
        TimekeeperLookupParams()
    with pytest.raises(ValidationError):
        TimekeeperLookupParams(timekeeper_id="tk1", email="x@y.com")
    with pytest.raises(ValidationError):
        TimekeeperLookupParams(timekeeper_id="tk1", vendor_id="v1")


@pytest.mark.unit
def test_timekeeper_lookup_by_timekeeper_id() -> None:
    tmpl = TimekeeperLookupTemplate()
    body = tmpl.build_query(TimekeeperLookupParams(timekeeper_id="tk_walker_partner"))
    assert body["query"]["bool"]["must"] == [{"term": {"timekeeper_id": "tk_walker_partner"}}]


@pytest.mark.unit
def test_timekeeper_lookup_by_email() -> None:
    tmpl = TimekeeperLookupTemplate()
    body = tmpl.build_query(TimekeeperLookupParams(email="patty@walker.com"))
    assert body["query"]["bool"]["must"] == [{"term": {"email": "patty@walker.com"}}]


@pytest.mark.unit
def test_timekeeper_lookup_active_filter_present_by_default() -> None:
    tmpl = TimekeeperLookupTemplate()
    body = tmpl.build_query(TimekeeperLookupParams(timekeeper_id="tk1"))
    assert {"term": {"active_status": "active"}} in body["query"]["bool"]["filter"]


@pytest.mark.unit
def test_timekeeper_lookup_template_metadata_open_to_any_role() -> None:
    tmpl = TimekeeperLookupTemplate()
    assert tmpl.allowed_roles == frozenset({"*"})
    assert tmpl.index == "vendor_lawyer_profiles_v1"
