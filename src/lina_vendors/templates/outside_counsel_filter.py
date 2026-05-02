"""outside_counsel_filter template — vendor/classification + rate-range bool filter."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

from lina_vendors.templates.base import VendorQueryTemplate

_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "timekeeper_id",
        "vendor_id",
        "vendor_name",
        "display_name",
        "email",
        "office_country_code",
        "bar_admissions",
        "jurisdictions",
        "practice_areas",
        "currency_code",
        "active_status",
        "timekeeper_classification",
        "standard_hourly_rate",
        "effective_hourly_rate",
        "years_of_experience",
    }
)


class OutsideCounselFilterParams(BaseModel):
    vendor_id: list[str] | None = None
    timekeeper_classification: list[str] | None = None
    practice_areas: list[str] | None = None
    jurisdictions: list[str] | None = None
    min_effective_hourly_rate: float | None = None
    max_effective_hourly_rate: float | None = None
    currency_code: str | None = None
    size: int | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _currency_required_with_rate_bounds(self) -> OutsideCounselFilterParams:
        if (
            self.min_effective_hourly_rate is not None or self.max_effective_hourly_rate is not None
        ) and self.currency_code is None:
            raise ValueError(
                "currency_code is required when min_effective_hourly_rate or "
                "max_effective_hourly_rate is provided"
            )
        return self


class OutsideCounselFilterTemplate(VendorQueryTemplate):
    query_type: ClassVar[str] = "outside_counsel_filter"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"legal_ops", "finance", "procurement"})
    Params: ClassVar[type[BaseModel]] = OutsideCounselFilterParams
    default_size: ClassVar[int] = 50
    max_size: ClassVar[int] = 500
    template_version: ClassVar[str] = "1.0.0"
    index: ClassVar[str] = "vendor_lawyer_profiles_v1"
    allowed_fields: ClassVar[frozenset[str]] = _ALLOWED_FIELDS

    def build_query(self, params: BaseModel) -> dict[str, Any]:
        assert isinstance(params, OutsideCounselFilterParams)

        must_clauses: list[dict[str, Any]] = []
        if params.vendor_id:
            must_clauses.append({"terms": {"vendor_id": list(params.vendor_id)}})
        if params.timekeeper_classification:
            must_clauses.append(
                {"terms": {"timekeeper_classification": list(params.timekeeper_classification)}}
            )
        if params.practice_areas:
            must_clauses.append({"terms": {"practice_areas": list(params.practice_areas)}})
        if params.jurisdictions:
            must_clauses.append({"terms": {"jurisdictions": list(params.jurisdictions)}})

        filter_clauses: list[dict[str, Any]] = []
        rate_range: dict[str, Any] = {}
        if params.min_effective_hourly_rate is not None:
            rate_range["gte"] = params.min_effective_hourly_rate
        if params.max_effective_hourly_rate is not None:
            rate_range["lte"] = params.max_effective_hourly_rate
        if rate_range:
            filter_clauses.append({"range": {"effective_hourly_rate": rate_range}})
            # currency_code is enforced by Params validator when rate range is set
            assert params.currency_code is not None
            filter_clauses.append({"term": {"currency_code": params.currency_code}})
        elif params.currency_code is not None:
            filter_clauses.append({"term": {"currency_code": params.currency_code}})

        if not must_clauses:
            must_clauses = [{"match_all": {}}]

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
