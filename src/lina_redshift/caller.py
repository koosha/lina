"""CallerContext model — identity supplied by Subsystem D to every worker call."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class CallerContext(BaseModel):
    user_id: Annotated[str, Field(min_length=1)]
    roles: frozenset[str]
    permission_tags: frozenset[str] = frozenset()
    request_id: Annotated[str, Field(min_length=1)]

    model_config = {"frozen": True}

    @field_validator("roles")
    @classmethod
    def _roles_non_empty(cls, v: frozenset[str]) -> frozenset[str]:
        if not v:
            raise ValueError("CallerContext.roles must contain at least one role")
        return v

    def has_any_role(self, allowed: frozenset[str]) -> bool:
        """Return True if the caller satisfies the template's allowed_roles.

        The wildcard sentinel {"*"} means "open to any caller with at least one role".
        """
        if "*" in allowed:
            return True
        return bool(self.roles & allowed)
