"""Unit tests for manager_chain template."""

from __future__ import annotations

from typing import Any

import pytest

from lina_users.templates.manager_chain import ManagerChainParams, ManagerChainTemplate


class _FakeClient:
    """In-memory client recording every search call."""

    def __init__(self, users: dict[str, dict[str, Any]]) -> None:
        self._users = users
        self.calls: list[dict[str, Any]] = []

    def search(self, *, index: str, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        self.calls.append({"index": index, "body": body})
        query = body.get("query", {})
        if "term" in query and "user_id" in query["term"]:
            uid = query["term"]["user_id"]
            user = self._users.get(uid)
            return {"hits": {"hits": [{"_source": user}] if user else []}}
        if "terms" in query and "manager_user_id" in query["terms"]:
            ids = query["terms"]["manager_user_id"]
            matches = [
                {"_source": u} for u in self._users.values() if u.get("manager_user_id") in ids
            ]
            return {"hits": {"hits": matches}}
        return {"hits": {"hits": []}}


@pytest.fixture
def chain_client() -> _FakeClient:
    users = {
        "user_alex_lee": {
            "user_id": "user_alex_lee",
            "display_name": "Alex Lee",
            "manager_user_id": "user_sam_rodriguez",
        },
        "user_sam_rodriguez": {
            "user_id": "user_sam_rodriguez",
            "display_name": "Sam Rodriguez",
            "manager_user_id": "user_chen_top",
        },
        "user_chen_top": {
            "user_id": "user_chen_top",
            "display_name": "Chen Top",
            "manager_user_id": None,
        },
        "user_jane_smith": {
            "user_id": "user_jane_smith",
            "display_name": "Jane Smith",
            "manager_user_id": "user_sam_rodriguez",
        },
    }
    return _FakeClient(users)


@pytest.mark.unit
def test_manager_chain_seed_query_targets_start_user() -> None:
    tmpl = ManagerChainTemplate()
    body = tmpl.build_query(ManagerChainParams(start_user_id="user_alex_lee"))
    assert body["query"] == {"term": {"user_id": "user_alex_lee"}}


@pytest.mark.unit
def test_manager_chain_walk_up_climbs_to_root(chain_client: _FakeClient) -> None:
    tmpl = ManagerChainTemplate()
    rows = tmpl.walk_chain(
        chain_client, ManagerChainParams(start_user_id="user_alex_lee", direction="up")
    )
    ids = [r["user_id"] for r in rows]
    assert ids == ["user_alex_lee", "user_sam_rodriguez", "user_chen_top"]


@pytest.mark.unit
def test_manager_chain_walk_up_respects_max_depth(chain_client: _FakeClient) -> None:
    tmpl = ManagerChainTemplate()
    rows = tmpl.walk_chain(
        chain_client,
        ManagerChainParams(start_user_id="user_alex_lee", direction="up", max_depth=1),
    )
    ids = [r["user_id"] for r in rows]
    assert ids == ["user_alex_lee", "user_sam_rodriguez"]


@pytest.mark.unit
def test_manager_chain_walk_down_collects_reports(chain_client: _FakeClient) -> None:
    tmpl = ManagerChainTemplate()
    rows = tmpl.walk_chain(
        chain_client,
        ManagerChainParams(start_user_id="user_sam_rodriguez", direction="down", max_depth=2),
    )
    ids = {r["user_id"] for r in rows}
    assert "user_sam_rodriguez" in ids
    assert "user_alex_lee" in ids
    assert "user_jane_smith" in ids


@pytest.mark.unit
def test_manager_chain_walk_handles_missing_start(chain_client: _FakeClient) -> None:
    tmpl = ManagerChainTemplate()
    rows = tmpl.walk_chain(
        chain_client,
        ManagerChainParams(start_user_id="user_does_not_exist", direction="up"),
    )
    assert rows == []


@pytest.mark.unit
def test_manager_chain_only_authorized_for_legal_or_hr_ops() -> None:
    tmpl = ManagerChainTemplate()
    assert tmpl.allowed_roles == frozenset({"legal_ops", "hr_ops"})
