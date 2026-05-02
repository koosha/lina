"""Generic ResultPacket and ErrorPacket — normalized worker output shapes.

Subsystems may subclass these to constrain `source_engine` and `schema_name`
to their own backend-specific literals.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class _ErrorBody(BaseModel):
    type: str
    message: str


class ResultPacket(BaseModel):
    """Generic normalized worker output. Subsystems may subclass to constrain fields."""

    source_engine: str
    schema_name: str = Field(default="", alias="schema")
    result_type: str
    metrics: list[dict[str, Any]]
    sql_trace_id: str
    row_count: int
    truncated: bool = False

    model_config = {"populate_by_name": True}


class ErrorPacket(BaseModel):
    """Generic normalized error output."""

    source_engine: str
    schema_name: str = Field(default="", alias="schema")
    result_type: str
    sql_trace_id: str
    error: _ErrorBody

    model_config = {"populate_by_name": True}

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        source_engine: str,
        schema_name: str,
        sql_trace_id: str,
        result_type: str,
    ) -> ErrorPacket:
        return cls.model_validate(
            {
                "source_engine": source_engine,
                "schema_name": schema_name,
                "result_type": result_type,
                "sql_trace_id": sql_trace_id,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
        )
