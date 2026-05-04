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

        worker_for_tool = {
            "query_redshift": self.redshift_worker,
            "search_users": self.users_worker,
            "search_vendors": self.vendors_worker,
        }
        if tool_name not in worker_for_tool:
            return {
                "source_engine": "supervisor",
                "result_type": tool_name,
                "error": {
                    "type": "UnknownToolError",
                    "message": f"no worker registered for tool {tool_name!r}",
                },
            }
        worker = worker_for_tool[tool_name]
        if worker is None:
            # The Lambda or CLI couldn't construct this worker (missing env
            # vars, network unreachable, etc.). Don't raise an
            # AttributeError — return a structured packet so the supervisor
            # can synthesize a "this source isn't available" reply.
            return {
                "source_engine": "supervisor",
                "result_type": tool_name,
                "error": {
                    "type": "BackendUnavailableError",
                    "message": (
                        f"the {tool_name!r} backend is not configured in this "
                        "environment; cannot serve this tool call"
                    ),
                },
            }

        packet = worker.run(
            query_type=query_type,
            params=params,
            caller=caller,
        )
        dumped: dict[str, Any] = packet.model_dump(by_alias=True)
        return dumped
