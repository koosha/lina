"""matter_lookup template — single-matter lookup over vw_matter_current."""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, model_validator

from lina_redshift.templates.base import QueryTemplate

_ALLOWED_OUTPUT_COLUMNS: frozenset[str] = frozenset(
    {
        "matter_id",
        "client_matter_id",
        "matter_name",
        "matter_status",
        "matter_type",
        "practice_area",
        "area_of_law_code",
        "open_date",
        "close_date",
        "matter_owner_user_id",
        "lead_inhouse_counsel_user_id",
        "business_unit",
        "cost_center_id",
        "budget_amount",
        "budget_currency_code",
    }
)


class MatterLookupParams(BaseModel):
    matter_id: str | None = None
    client_matter_id: str | None = None
    matter_owner_user_id: str | None = None
    include_closed: bool = False
    limit: int | None = None

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _exactly_one_lookup(self) -> MatterLookupParams:
        provided = [
            v
            for v in (self.matter_id, self.client_matter_id, self.matter_owner_user_id)
            if v is not None
        ]
        if len(provided) != 1:
            raise ValueError(
                "exactly one of matter_id, client_matter_id, matter_owner_user_id is required"
            )
        return self


class MatterLookupTemplate(QueryTemplate):
    query_type: ClassVar[str] = "matter_lookup"
    allowed_roles: ClassVar[frozenset[str]] = frozenset({"*"})
    Params: ClassVar[type[BaseModel]] = MatterLookupParams
    default_limit: ClassVar[int] = 100
    max_limit: ClassVar[int] = 1_000
    template_version: ClassVar[str] = "1.0.0"

    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        assert isinstance(params, MatterLookupParams)
        if params.matter_id is not None:
            where = "matter_id = %(matter_id)s"
            binds: dict[str, Any] = {"matter_id": params.matter_id}
        elif params.client_matter_id is not None:
            where = "client_matter_id = %(client_matter_id)s"
            binds = {"client_matter_id": params.client_matter_id}
        else:
            where = "matter_owner_user_id = %(matter_owner_user_id)s"
            binds = {"matter_owner_user_id": params.matter_owner_user_id}

        if not params.include_closed:
            where = f"({where}) AND matter_status <> 'closed'"

        effective_limit = min(params.limit or self.default_limit, self.max_limit)
        binds["limit"] = effective_limit

        sql = (
            "SELECT matter_id, client_matter_id, matter_name, matter_status, "
            "matter_type, practice_area, area_of_law_code, open_date, close_date, "
            "matter_owner_user_id, lead_inhouse_counsel_user_id, business_unit, "
            "cost_center_id, budget_amount, budget_currency_code "
            f"FROM vw_matter_current WHERE {where} LIMIT %(limit)s"
        )
        return sql, binds

    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in row.items() if k in _ALLOWED_OUTPUT_COLUMNS} for row in rows]
