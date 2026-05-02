"""user_search template — multi-match on display name / job title with filters."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from lina_users.templates.base import UserQueryTemplate

_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "user_id",
        "employee_id",
        "email",
        "first_name",
        "last_name",
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


class UserSearchParams(BaseModel):
    query: str = ""
    department: list[str] | None = None
    business_unit: list[str] | None = None
    region: list[str] | None = None
    user_status: list[str] | None = None
    size: int | None = None

    model_config = {"frozen": True}


class UserSearchTemplate(UserQueryTemplate):
    query_type: ClassVar[str] = "user_search"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"*"})
    Params: ClassVar[type[BaseModel]] = UserSearchParams
    default_size: ClassVar[int] = 25
    max_size: ClassVar[int] = 200
    template_version: ClassVar[str] = "1.0.0"
    index: ClassVar[str] = "corp_user_profiles_v1"
    allowed_fields: ClassVar[frozenset[str]] = _ALLOWED_FIELDS

    def build_query(self, params: BaseModel) -> dict[str, Any]:
        assert isinstance(params, UserSearchParams)

        if params.query:
            must_clauses: list[dict[str, Any]] = [
                {
                    "multi_match": {
                        "query": params.query,
                        "fields": [
                            "display_name^2",
                            "first_name",
                            "last_name",
                            "job_title",
                            "email_text",
                        ],
                        "type": "best_fields",
                    }
                }
            ]
        else:
            must_clauses = [{"match_all": {}}]

        filter_clauses: list[dict[str, Any]] = []
        if params.department:
            filter_clauses.append({"terms": {"department": list(params.department)}})
        if params.business_unit:
            filter_clauses.append({"terms": {"business_unit": list(params.business_unit)}})
        if params.region:
            filter_clauses.append({"terms": {"region": list(params.region)}})
        if params.user_status:
            filter_clauses.append({"terms": {"user_status": list(params.user_status)}})

        body: dict[str, Any] = {
            "size": min(params.size or self.default_size, self.max_size),
            "_source": sorted(_ALLOWED_FIELDS),
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses,
                }
            },
        }
        return body

    def shape_packet(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {k: v for k, v in (hit.get("_source") or {}).items() if k in _ALLOWED_FIELDS}
            for hit in hits
        ]
