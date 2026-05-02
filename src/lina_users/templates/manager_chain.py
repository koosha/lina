"""manager_chain template — walk reporting chain via manager_user_id."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel

from lina_users.templates.base import UserQueryTemplate

_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "user_id",
        "display_name",
        "job_title",
        "department",
        "business_unit",
        "manager_user_id",
        "region",
        "country_code",
        "user_status",
        "user_type",
    }
)


class ManagerChainParams(BaseModel):
    start_user_id: str = ""
    direction: Literal["up", "down"] = "up"
    max_depth: int = 5
    size: int | None = None

    model_config = {"frozen": True}


class ManagerChainTemplate(UserQueryTemplate):
    """Multi-hop user query template — worker dispatches to `walk_chain` instead of single search."""

    query_type: ClassVar[str] = "manager_chain"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"legal_ops", "hr_ops"})
    Params: ClassVar[type[BaseModel]] = ManagerChainParams
    default_size: ClassVar[int] = 25
    max_size: ClassVar[int] = 100
    template_version: ClassVar[str] = "1.0.0"
    index: ClassVar[str] = "corp_user_profiles_v1"
    allowed_fields: ClassVar[frozenset[str]] = _ALLOWED_FIELDS

    def build_query(self, params: BaseModel) -> dict[str, Any]:
        """Return the *seed* term query for `start_user_id`. Worker uses this for the first hop."""
        assert isinstance(params, ManagerChainParams)
        body: dict[str, Any] = {
            "size": 1,
            "_source": sorted(_ALLOWED_FIELDS),
            "query": {"term": {"user_id": params.start_user_id}},
        }
        return body

    def shape_packet(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in (hit.get("_source") or {}).items() if k in _ALLOWED_FIELDS}
            for hit in hits
        ]

    def walk_chain(self, client: Any, params: BaseModel) -> list[dict[str, Any]]:
        """Iteratively walk the reporting chain up or down, capped by `max_depth`.

        Returns a list of `_source` dicts (not yet shaped) ordered from `start_user_id`
        outward. The starting user is the first element when present.
        """
        assert isinstance(params, ManagerChainParams)
        if not params.start_user_id:
            return []

        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        if params.direction == "up":
            current_id: str | None = params.start_user_id
            depth = 0
            while current_id and depth < params.max_depth + 1:
                if current_id in seen:
                    break
                seen.add(current_id)
                resp = client.search(
                    index=self.index,
                    body={
                        "size": 1,
                        "_source": sorted(_ALLOWED_FIELDS),
                        "query": {"term": {"user_id": current_id}},
                    },
                )
                hits = resp.get("hits", {}).get("hits", [])
                if not hits:
                    break
                source = hits[0].get("_source") or {}
                results.append(source)
                current_id = source.get("manager_user_id")
                depth += 1
            return results

        # direction == "down": breadth-first by manager_user_id
        frontier: list[str] = [params.start_user_id]
        depth = 0
        # First emit the seed user.
        seed_resp = client.search(
            index=self.index,
            body={
                "size": 1,
                "_source": sorted(_ALLOWED_FIELDS),
                "query": {"term": {"user_id": params.start_user_id}},
            },
        )
        seed_hits = seed_resp.get("hits", {}).get("hits", [])
        if seed_hits:
            seed_source = seed_hits[0].get("_source") or {}
            results.append(seed_source)
            seen.add(params.start_user_id)
        while frontier and depth < params.max_depth:
            resp = client.search(
                index=self.index,
                body={
                    "size": min(params.size or self.default_size, self.max_size),
                    "_source": sorted(_ALLOWED_FIELDS),
                    "query": {"terms": {"manager_user_id": frontier}},
                },
            )
            hits = resp.get("hits", {}).get("hits", [])
            next_frontier: list[str] = []
            for hit in hits:
                source = hit.get("_source") or {}
                uid = source.get("user_id")
                if uid and uid not in seen:
                    seen.add(uid)
                    results.append(source)
                    next_frontier.append(uid)
            frontier = next_frontier
            depth += 1
        return results
