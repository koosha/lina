"""WorkerHub: dispatches LLM tool calls to the right subsystem worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lina_core.caller import CallerContext


@dataclass
class WorkerHub:
    """Façade routing an LLM tool call to the correct worker.

    Workers are typed as ``Any`` to avoid hard-import dependencies in tests
    that mock the worker interfaces.
    """

    redshift_worker: Any
    users_worker: Any
    vendors_worker: Any

    def dispatch(
        self,
        *,
        tool_name: str,
        tool_input: dict[str, Any],
        caller: CallerContext,
    ) -> dict[str, Any]:
        """Run the tool call and return a JSON-serializable packet dict."""
        query_type = tool_input.get("query_type", "")
        params = tool_input.get("params", {})

        if tool_name == "query_redshift":
            packet = self.redshift_worker.run(
                query_type=query_type,
                params=params,
                caller=caller,
            )
        elif tool_name == "search_users":
            packet = self.users_worker.run(
                query_type=query_type,
                params=params,
                caller=caller,
            )
        elif tool_name == "search_vendors":
            packet = self.vendors_worker.run(
                query_type=query_type,
                params=params,
                caller=caller,
            )
        else:
            return {
                "source_engine": "supervisor",
                "result_type": tool_name,
                "error": {
                    "type": "UnknownToolError",
                    "message": f"no worker registered for tool {tool_name!r}",
                },
            }

        dumped: dict[str, Any] = packet.model_dump(by_alias=True)
        return dumped
