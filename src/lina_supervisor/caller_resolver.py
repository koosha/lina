"""Resolve a user_id into a fully populated CallerContext via Subsystem A.

The supervisor calls Subsystem A's ``user_lookup`` template internally, using
a hidden bootstrap caller identity that is only authorized for ``user_lookup``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lina_core.caller import CallerContext

_BOOTSTRAP_CALLER = CallerContext(
    user_id="lina_supervisor_bootstrap",
    roles=frozenset({"caller_resolver"}),
    permission_tags=frozenset(),
    request_id="bootstrap",
)


class UserNotFoundError(RuntimeError):
    """Raised when ``user_lookup`` returns no profile for the requested user_id."""


@dataclass
class CallerResolver:
    """Resolve a CLI ``--user-id`` into the full CallerContext."""

    users_worker: Any  # UserSearchWorker; typed as Any to avoid hard import dependency

    def resolve(self, *, user_id: str, request_id: str) -> CallerContext:
        packet = self.users_worker.run(
            query_type="user_lookup",
            params={"user_id": user_id},
            caller=_BOOTSTRAP_CALLER,
        )
        metrics = getattr(packet, "metrics", None)
        if not metrics:
            raise UserNotFoundError(f"user_id {user_id!r} not found")
        profile: dict[str, Any] = metrics[0]
        roles = frozenset(profile.get("roles", []) or []) or frozenset({"reader"})
        permission_tags = frozenset(profile.get("permission_tags", []) or [])
        return CallerContext(
            user_id=profile["user_id"],
            roles=roles,
            permission_tags=permission_tags,
            request_id=request_id,
        )
