"""SupervisorResponse — final shape returned by lina-chat."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SupervisorResponse(BaseModel):
    source_engine: Literal["supervisor"] = "supervisor"
    session_id: str
    request_id: str
    user_id: str
    answer_text: str
    worker_packets: list[dict[str, Any]] = Field(default_factory=list)
    worker_call_count: int = 0
    truncated: bool = False
    model: str
    duration_ms: int
    sql_trace_id: str
