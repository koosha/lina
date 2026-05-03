"""Lambda entry shim. Re-exports the handler from the lina_supervisor package."""

from lina_supervisor.lambda_handler import handler

__all__ = ["handler"]
