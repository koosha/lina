"""Vendor-search-specific ResultPacket and ErrorPacket — preset source_engine/schema."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from lina_core.packet import ErrorPacket as _CoreErrorPacket
from lina_core.packet import ResultPacket as _CoreResultPacket
from lina_core.packet import _ErrorBody


class ResultPacket(_CoreResultPacket):
    source_engine: Literal["opensearch"] = "opensearch"
    schema_name: Literal["vendor_lawyer_profiles_v1"] = Field(
        default="vendor_lawyer_profiles_v1",
        alias="schema",
    )


class ErrorPacket(_CoreErrorPacket):
    source_engine: Literal["opensearch"] = "opensearch"
    schema_name: Literal["vendor_lawyer_profiles_v1"] = Field(
        default="vendor_lawyer_profiles_v1",
        alias="schema",
    )

    @classmethod
    def from_exception(  # type: ignore[override]
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
