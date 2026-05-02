"""people_filter template — bool.must of terms across keyword fields."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from lina_users.templates.base import UserQueryTemplate

_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "user_id",
        "employee_id",
        "email",
        "display_name",
        "job_title",
        "department",
        "business_unit",
        "cost_center",
        "manager_user_id",
        "region",
        "country_code",
        "user_status",
        "user_type",
        "roles",
        "permission_tags",
        "legal_team_role",
        "practice_area_focus",
    }
)


class PeopleFilterParams(BaseModel):
    department: list[str] | None = None
    business_unit: list[str] | None = None
    roles: list[str] | None = None
    permission_tags: list[str] | None = None
    user_status: list[str] | None = None
    region: list[str] | None = None
    legal_team_role: list[str] | None = None
    size: int | None = None

    model_config = {"frozen": True}


class PeopleFilterTemplate(UserQueryTemplate):
    query_type: ClassVar[str] = "people_filter"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"*"})
    Params: ClassVar[type[BaseModel]] = PeopleFilterParams
    default_size: ClassVar[int] = 50
    max_size: ClassVar[int] = 500
    template_version: ClassVar[str] = "1.0.0"
    index: ClassVar[str] = "corp_user_profiles_v1"
    allowed_fields: ClassVar[frozenset[str]] = _ALLOWED_FIELDS

    def build_query(self, params: BaseModel) -> dict[str, Any]:
        assert isinstance(params, PeopleFilterParams)

        must_clauses: list[dict[str, Any]] = []
        if params.department:
            must_clauses.append({"terms": {"department": list(params.department)}})
        if params.business_unit:
            must_clauses.append({"terms": {"business_unit": list(params.business_unit)}})
        if params.roles:
            must_clauses.append({"terms": {"roles": list(params.roles)}})
        if params.permission_tags:
            must_clauses.append({"terms": {"permission_tags": list(params.permission_tags)}})
        if params.user_status:
            must_clauses.append({"terms": {"user_status": list(params.user_status)}})
        if params.region:
            must_clauses.append({"terms": {"region": list(params.region)}})
        if params.legal_team_role:
            must_clauses.append({"terms": {"legal_team_role": list(params.legal_team_role)}})

        if not must_clauses:
            must_clauses = [{"match_all": {}}]

        body: dict[str, Any] = {
            "size": min(params.size or self.default_size, self.max_size),
            "_source": sorted(_ALLOWED_FIELDS),
            "query": {"bool": {"must": must_clauses}},
        }
        return body

    def shape_packet(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in (hit.get("_source") or {}).items() if k in _ALLOWED_FIELDS}
            for hit in hits
        ]
