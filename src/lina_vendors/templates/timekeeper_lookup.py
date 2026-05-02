"""timekeeper_lookup template — single-timekeeper lookup by id/email/(vendor_id+name)."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

from lina_vendors.templates.base import VendorQueryTemplate

_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "timekeeper_id",
        "vendor_id",
        "vendor_name",
        "first_name",
        "last_name",
        "display_name",
        "email",
        "phone_number",
        "office_country_code",
        "office_state_province",
        "office_city",
        "office_postal_code",
        "bar_admissions",
        "jurisdictions",
        "industries",
        "practice_areas",
        "currency_code",
        "active_status",
        "timekeeper_classification",
        "standard_hourly_rate",
        "effective_hourly_rate",
        "years_of_experience",
        "expertise_summary",
        "representative_matters_summary",
        "source_system",
    }
)


class TimekeeperLookupParams(BaseModel):
    timekeeper_id: str | None = None
    email: str | None = None
    vendor_id: str | None = None
    display_name: str | None = None
    include_inactive: bool = False
    size: int | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _exactly_one_lookup(self) -> TimekeeperLookupParams:
        provided_singletons = [v for v in (self.timekeeper_id, self.email) if v is not None]
        # vendor_id alone or paired with display_name counts as one selector
        has_vendor_combo = self.vendor_id is not None
        provided_count = len(provided_singletons) + (1 if has_vendor_combo else 0)
        if provided_count != 1:
            raise ValueError(
                "exactly one of timekeeper_id, email, or vendor_id (with optional "
                "display_name) is required"
            )
        return self


class TimekeeperLookupTemplate(VendorQueryTemplate):
    query_type: ClassVar[str] = "timekeeper_lookup"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"*"})
    Params: ClassVar[type[BaseModel]] = TimekeeperLookupParams
    default_size: ClassVar[int] = 1
    max_size: ClassVar[int] = 25
    template_version: ClassVar[str] = "1.0.0"
    index: ClassVar[str] = "vendor_lawyer_profiles_v1"
    allowed_fields: ClassVar[frozenset[str]] = _ALLOWED_FIELDS

    def build_query(self, params: BaseModel) -> dict[str, Any]:
        assert isinstance(params, TimekeeperLookupParams)
        if params.timekeeper_id is not None:
            must_clauses: list[dict[str, Any]] = [{"term": {"timekeeper_id": params.timekeeper_id}}]
        elif params.email is not None:
            must_clauses = [{"term": {"email": params.email}}]
        elif params.vendor_id is not None:
            must_clauses = [{"term": {"vendor_id": params.vendor_id}}]
            if params.display_name is not None:
                must_clauses.append({"term": {"display_name.keyword": params.display_name}})
        else:
            # pre-import construct: validation hasn't run yet
            must_clauses = [{"term": {"timekeeper_id": ""}}]

        filter_clauses: list[dict[str, Any]] = []
        if not params.include_inactive:
            filter_clauses.append({"term": {"active_status": "active"}})

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
