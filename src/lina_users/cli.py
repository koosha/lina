"""`lina-users` CLI entry point — Click-based, JSON stdout, structured stderr."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import click

from lina_core.logging_config import configure_logging
from lina_users.connection import open_client, resolve_config
from lina_users.indices.runner import IndexRunner, list_pending


def _mappings_dir() -> Path:
    return Path(str(resources.files("lina_users.indices").joinpath("mappings")))


@click.group()
@click.pass_context
def main(ctx: click.Context) -> None:
    configure_logging()
    ctx.ensure_object(dict)


def _get_client(ctx: click.Context) -> Any:
    """Lazily resolve the OpenSearch client. Skipped for commands that don't need it."""
    if "client" not in ctx.obj:
        cfg = resolve_config()
        ctx.obj["config"] = cfg
        ctx.obj["client"] = open_client(cfg)
    return ctx.obj["client"]


@main.group()
def indices() -> None:
    """Index lifecycle commands."""


@indices.command("apply")
@click.pass_context
def indices_apply(ctx: click.Context) -> None:
    client = _get_client(ctx)
    runner = IndexRunner(client=client, mappings_dir=_mappings_dir())
    applied = runner.apply_pending()
    click.echo(json.dumps({"applied": len(applied), "versions": applied}, indent=2))


@indices.command("status")
@click.pass_context
def indices_status(ctx: click.Context) -> None:
    client = _get_client(ctx)
    pending = list_pending(client=client, mappings_dir=_mappings_dir())
    all_versions = sorted(p.stem for p in _mappings_dir().glob("*.json"))
    applied = [v for v in all_versions if v not in pending]
    click.echo(json.dumps({"applied": applied, "pending": pending}, indent=2))


@main.command("seed")
@click.option("--reset", is_flag=True, default=False)
@click.option("--named-only", "named_only", is_flag=True, default=False)
@click.option("--bulk-only", "bulk_only", is_flag=True, default=False)
@click.pass_context
def seed_cmd(ctx: click.Context, reset: bool, named_only: bool, bulk_only: bool) -> None:
    if named_only and bulk_only:
        raise click.UsageError("--named-only and --bulk-only are mutually exclusive")

    from opensearchpy import helpers

    from lina_users.seed import load_all
    from lina_users.seed.generator import generate_users
    from lina_users.seed.named_entities import named_user_docs

    client = _get_client(ctx)
    if named_only:
        runner = IndexRunner(client=client, mappings_dir=_mappings_dir())
        if reset and client.indices.exists(index="corp_user_profiles_v1"):
            client.indices.delete(index="corp_user_profiles_v1")
        runner.apply_pending()
        actions = [
            {"_index": "corp_user_profiles_v1", "_id": d["user_id"], "_source": d}
            for d in named_user_docs()
        ]
        helpers.bulk(client, actions, refresh="wait_for")
        result = {"named": len(actions), "generated": 0, "total": len(actions)}
    elif bulk_only:
        runner = IndexRunner(client=client, mappings_dir=_mappings_dir())
        runner.apply_pending()
        gen = generate_users(count=50, seed=42)
        actions = [
            {"_index": "corp_user_profiles_v1", "_id": d["user_id"], "_source": d} for d in gen
        ]
        helpers.bulk(client, actions, refresh="wait_for")
        result = {"named": 0, "generated": len(gen), "total": len(gen)}
    else:
        result = load_all(client, reset=reset)
    click.echo(json.dumps({"loaded": True, "reset": reset, **result}, indent=2))


@main.command("list-templates")
def list_templates_cmd() -> None:
    from lina_users.templates import all_templates

    payload = [
        {
            "query_type": t.query_type,
            "allowed_roles": sorted(t.allowed_roles),
            "default_size": t.default_size,
            "max_size": t.max_size,
            "template_version": t.template_version,
            "index": t.index,
            "params_schema": t.Params.model_json_schema(),
        }
        for t in all_templates()
    ]
    click.echo(json.dumps(payload, indent=2, default=str))


@main.command("run")
@click.argument("query_type")
@click.option("--params", required=True)
@click.option("--user-id", "user_id", required=True)
@click.option("--caller-roles", "caller_roles", required=True, help="Comma-separated roles")
@click.option("--request-id", "request_id", default="cli_request")
@click.pass_context
def run_cmd(
    ctx: click.Context,
    query_type: str,
    params: str,
    user_id: str,
    caller_roles: str,
    request_id: str,
) -> None:
    from lina_core.caller import CallerContext
    from lina_users.worker import UserSearchWorker

    client = _get_client(ctx)
    cfg = ctx.obj["config"]
    parsed_params = json.loads(params)
    caller = CallerContext(
        user_id=user_id,
        roles=frozenset(r.strip() for r in caller_roles.split(",") if r.strip()),
        request_id=request_id,
    )
    worker = UserSearchWorker(client=client, config=cfg)
    packet = worker.run(query_type=query_type, params=parsed_params, caller=caller)
    click.echo(packet.model_dump_json(by_alias=True, indent=2))


@main.command("explain")
@click.argument("query_type")
@click.option("--params", required=True)
@click.pass_context
def explain_cmd(ctx: click.Context, query_type: str, params: str) -> None:
    from lina_users.templates import get_template

    client = _get_client(ctx)
    template = get_template(query_type)
    parsed_params = json.loads(params)
    parsed = template.Params.model_validate(parsed_params)
    body = template.build_query(parsed)

    explain_plan: list[object] | None = None
    try:
        resp = client.search(index=template.index, body=body, explain=True)
        hits = resp.get("hits", {}).get("hits", [])
        explain_plan = [hit.get("_explanation") for hit in hits]
    except Exception as exc:  # noqa: BLE001 — explain is best-effort
        explain_plan = [{"error": str(exc)}]

    click.echo(
        json.dumps(
            {
                "query_type": query_type,
                "index": template.index,
                "sql": body,
                "explain_plan": explain_plan,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
