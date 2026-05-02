"""QueryTemplate ABC and the at-import AST sanity checker."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import sqlglot
from pydantic import BaseModel
from sqlglot import ErrorLevel, TokenType, exp

APPROVED_RELATIONS: frozenset[str] = frozenset({
    "vw_matter_current",
    "mv_matter_spend_summary",
    "mv_vendor_spend_summary",
    "mv_timekeeper_rate_analysis",
    "fact_invoice",
    "fact_invoice_line_item",
})

ALLOWED_FUNCTIONS: frozenset[str] = frozenset({
    "sum", "count", "avg", "min", "max",
    "coalesce", "nullif",
    "to_char", "date_trunc", "extract",
    "abs", "round", "greatest", "least",
})


class TemplateValidationError(RuntimeError):
    """Raised when a template's SQL violates the spec §13 rules."""


_BANNED_TOKEN_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|CREATE|ALTER|DROP|TRUNCATE|UNLOAD|COPY)\b",
    flags=re.IGNORECASE,
)


def _extract_function_calls(sql: str) -> list[str]:
    """Return lowercase identifier tokens that immediately precede an L_PAREN.

    sqlglot's strict parser rejects single-arg forms of functions like
    ``to_char(x)`` because their schema requires more arguments. To keep the
    function-name allowlist independent of those AST-level constraints we
    detect call sites at the token level instead.
    """
    tokens = list(sqlglot.tokenize(sql, read="redshift"))
    calls: list[str] = []
    for i, tok in enumerate(tokens[:-1]):
        next_tok = tokens[i + 1]
        if next_tok.token_type is not TokenType.L_PAREN:
            continue
        # Function calls appear as identifier-like tokens followed by '('.
        # Skip non-identifier tokens (operators, punctuation, etc.).
        if not tok.text or not re.match(r"[A-Za-z_][A-Za-z_0-9]*$", tok.text):
            continue
        calls.append(tok.text.lower())
    return calls


def validate_template_sql(sql: str) -> None:
    """Run the AST sanity checks for spec §13 rules 1, 2, 5, 6, 10, 11, 12, 13.

    Rules 3, 4, 7, 8, 9 are enforced at runtime in the worker, not here.
    """
    # Rule 10/11/12: regex-level token sanity check before parsing.
    banned = _BANNED_TOKEN_RE.search(sql)
    if banned:
        raise TemplateValidationError(
            f"SQL contains banned token {banned.group(0)!r}: {sql!r}"
        )

    # Rule 13 (token-level): every function call must be in ALLOWED_FUNCTIONS.
    # Performed pre-parse because sqlglot's strict mode rejects some
    # single-argument forms (to_char, date_trunc, ...) we still want to allow.
    for fn_name in _extract_function_calls(sql):
        if fn_name not in ALLOWED_FUNCTIONS:
            raise TemplateValidationError(
                f"function {fn_name!r} is not in ALLOWED_FUNCTIONS"
            )

    # Parse with Redshift dialect; IGNORE level so single-arg forms parse.
    try:
        tree = sqlglot.parse_one(sql, read="redshift", error_level=ErrorLevel.IGNORE)
    except sqlglot.errors.ParseError as exc:
        raise TemplateValidationError(f"could not parse SQL: {exc}") from exc

    if tree is None:
        raise TemplateValidationError("template SQL must be exactly one SELECT statement")

    # Rule 1: must be a SELECT.
    if not isinstance(tree, exp.Select):
        raise TemplateValidationError(
            f"only SELECT statements are allowed; got {tree.key}"
        )

    # Rule 2: every referenced table must be in APPROVED_RELATIONS.
    for table in tree.find_all(exp.Table):
        name = table.name
        if name not in APPROVED_RELATIONS:
            raise TemplateValidationError(
                f"relation {name!r} is not in APPROVED_RELATIONS"
            )

    # Rule 5: no FROM-clause joins in template SQL (joins live inside MVs).
    for join in tree.find_all(exp.Join):
        raise TemplateValidationError(
            f"template must not contain join clauses; found {join.sql(dialect='redshift')!r}"
        )

    # Rule 6: must contain a LIMIT clause (parameter binding allowed).
    if not tree.args.get("limit"):
        raise TemplateValidationError("template SQL must contain a LIMIT clause")


class QueryTemplate(ABC):
    query_type: ClassVar[str]
    allowed_roles: ClassVar[frozenset[str]]
    Params: ClassVar[type[BaseModel]]
    default_limit: ClassVar[int]
    max_limit: ClassVar[int]
    template_version: ClassVar[str]

    @abstractmethod
    def build_sql(self, params: BaseModel) -> tuple[str, dict[str, Any]]:
        """Return (sql_with_named_binds, parameter_dict)."""

    @abstractmethod
    def shape_packet(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Project rows to the template's allowlisted columns."""

    def validate_at_import(self) -> None:
        """Run AST sanity check against a representative SQL produced by build_sql."""
        params = self.Params.model_construct()
        sql, _binds = self.build_sql(params)
        validate_template_sql(sql)
