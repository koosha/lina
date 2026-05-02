"""ResultPacket and ErrorPacket — normalized worker output shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ResultPacket(BaseModel):
    source_engine: Literal["redshift"] = "redshift"
    schema_name: Literal["legal_matter_spend"] = Field(
        default="legal_matter_spend", alias="schema",
    )
    result_type: str
    metrics: list[dict[str, Any]]
    sql_trace_id: str
    row_count: int
    truncated: bool = False

    model_config = {"populate_by_name": True}


class _ErrorBody(BaseModel):
    type: str
    message: str


class ErrorPacket(BaseModel):
    source_engine: Literal["redshift"] = "redshift"
    schema_name: Literal["legal_matter_spend"] = Field(
        default="legal_matter_spend", alias="schema",
    )
    result_type: str
    sql_trace_id: str
    error: _ErrorBody

    model_config = {"populate_by_name": True}

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        sql_trace_id: str,
        result_type: str,
    ) -> ErrorPacket:
        return cls(
            result_type=result_type,
            sql_trace_id=sql_trace_id,
            error=_ErrorBody(type=type(exc).__name__, message=str(exc)),
        )
