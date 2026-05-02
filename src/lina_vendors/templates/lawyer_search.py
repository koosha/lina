"""lawyer_search template — multi-match across names + expertise with filter facets."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

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
        "office_country_code",
        "office_state_province",
        "office_city",
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
    }
)


class LawyerSearchParams(BaseModel):
    query: str = ""
    practice_areas: list[str] | None = None
    jurisdictions: list[str] | None = None
    bar_admissions: list[str] | None = None
    active_status: list[str] | None = None
    size: int | None = None

    model_config = {"frozen": True}


class LawyerSearchTemplate(VendorQueryTemplate):
    query_type: ClassVar[str] = "lawyer_search"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"*"})
    Params: ClassVar[type[BaseModel]] = LawyerSearchParams
    default_size: ClassVar[int] = 25
    max_size: ClassVar[int] = 200
    template_version: ClassVar[str] = "1.0.0"
    index: ClassVar[str] = "vendor_lawyer_profiles_v1"
    allowed_fields: ClassVar[frozenset[str]] = _ALLOWED_FIELDS

    def build_query(self, params: BaseModel) -> dict[str, Any]:
        assert isinstance(params, LawyerSearchParams)

        if params.query:
            must_clauses: list[dict[str, Any]] = [
                {
                    "multi_match": {
                        "query": params.query,
                        "fields": [
                            "display_name^2",
                            "first_name",
                            "last_name",
                            "vendor_name",
                            "expertise_summary",
                        ],
                        "type": "best_fields",
                    }
                }
            ]
        else:
            must_clauses = [{"match_all": {}}]

        filter_clauses: list[dict[str, Any]] = []
        if params.practice_areas:
            filter_clauses.append({"terms": {"practice_areas": list(params.practice_areas)}})
        if params.jurisdictions:
            filter_clauses.append({"terms": {"jurisdictions": list(params.jurisdictions)}})
        if params.bar_admissions:
            filter_clauses.append({"terms": {"bar_admissions": list(params.bar_admissions)}})
        if params.active_status:
            filter_clauses.append({"terms": {"active_status": list(params.active_status)}})

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
