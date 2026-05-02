"""user_lookup template — single-user lookup by id/email/employee_id."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

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


class UserLookupParams(BaseModel):
    user_id: str | None = None
    email: str | None = None
    employee_id: str | None = None
    include_inactive: bool = False
    size: int | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _exactly_one_lookup(self) -> UserLookupParams:
        provided = [v for v in (self.user_id, self.email, self.employee_id) if v is not None]
        if len(provided) != 1:
            raise ValueError("exactly one of user_id, email, employee_id is required")
        return self


class UserLookupTemplate(UserQueryTemplate):
    query_type: ClassVar[str] = "user_lookup"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"*"})
    Params: ClassVar[type[BaseModel]] = UserLookupParams
    default_size: ClassVar[int] = 1
    max_size: ClassVar[int] = 10
    template_version: ClassVar[str] = "1.0.0"
    index: ClassVar[str] = "corp_user_profiles_v1"
    allowed_fields: ClassVar[frozenset[str]] = _ALLOWED_FIELDS

    def build_query(self, params: BaseModel) -> dict[str, Any]:
        assert isinstance(params, UserLookupParams)
        if params.user_id is not None:
            term = {"user_id": params.user_id}
        elif params.email is not None:
            term = {"email": params.email}
        elif params.employee_id is not None:
            term = {"employee_id": params.employee_id}
        else:
            # Validation in build (pre-import construct can have all-None params)
            term = {"user_id": ""}

        must_clauses: list[dict[str, Any]] = [{"term": term}]
        filter_clauses: list[dict[str, Any]] = []
        if not params.include_inactive:
            filter_clauses.append({"term": {"user_status": "active"}})

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
