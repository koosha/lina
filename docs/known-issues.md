# Known Issues

Append-only log. Newest at the top. Each entry: severity · status · short
description · repro · likely cause · fix sketch.

Severities:
- **P1** — blocks a core demo path or could lose/corrupt data.
- **P2** — degrades the demo (wrong answer, ugly fallback) but workable.
- **P3** — cosmetic or rare edge case.

---

## 2026-05-03 · P2 · open · CI integration suite has four pre-existing failures

The `ci-integration.yml` workflow has been red on multiple recent runs.
Tests are not modified by branches that touch the supervisor or web UI;
all four failures live in `tests/integration/` and the failure modes
suggest sandbox-state drift, not regression.

**Failures (run 25294448709, branch `feat/ui-direction-d`):**

1. `tests/integration/lina_users/test_aws_smoke.py::test_user_search_against_aws_opensearch`
   — `user_search` query for `{"query": "Counsel", "department": ["Legal"]}`
   returned 0 rows. `user_lookup` against the same index passed in the
   same run, so the index is populated; the search/filter path is the
   gap. Possibly a refresh-interval race after `seed --reset` or a
   permission_tag filter mismatch with the `legal_ops_caller` fixture.

2. `tests/integration/lina_users/test_aws_smoke.py::test_people_filter_against_aws_opensearch`
   — same shape, `people_filter` with `{"department": ["Legal"], "user_status": ["active"]}`.

3. `tests/integration/lina_vendors/test_aws_smoke.py::test_outside_counsel_filter_against_aws_opensearch`
   — same shape, `outside_counsel_filter` with `{"vendor_id": ["vendor_walker"], "currency_code": "USD"}`.

4. `tests/integration/test_redshift_dialect_parity.py::test_views_and_mvs_exist_in_redshift`
   — `psycopg2.errors.InsufficientPrivilege: permission denied for relation stv_mv_info`.
   The CI `lina_admin` role doesn't have privileges on `stv_mv_info`.
   Either grant `SYSLOG ACCESS UNRESTRICTED` to the role, or query
   `pg_namespace`/`pg_class` for the materialized views instead.

**Fix sketch:**

- For 1–3, after `seed --reset` add `client.indices.refresh(index="*")`
  to the seed CLI's tail or insert a 1-second sleep / explicit refresh
  call in the CI workflow. If that doesn't help, rerun the suite
  locally against the sandbox to see whether it's permission_tag
  filtering or a true seed-data gap.
- For 4, change the test to either use a SQL view available to
  `lina_admin` or grant the role access via a Redshift `ALTER USER`.

**Surfaced in:** PR #2 CI run 25294448709 on 2026-05-03. The PR's own
code changes do not touch any of the failing tests or their fixtures
(`git log main..feat/ui-direction-d -- tests/` is empty).

---

## 2026-05-03 · P2 · fixed · supervisor called `user_lookup` with empty params

**Repro (was):** ask Lina "What is user_jane_smith's job title and
department?" through the live UI. The worker returned an
`InvalidParametersError` saying "exactly one of user_id, email,
employee_id is required" and the supervisor surfaced that as
"the User Profiles lookup tool isn't accepting user_id" — making it
look like the validator was the bug.

**Actual cause:** the validator was correct. The OpenAI tool definitions
in `src/lina_supervisor/tools.py` keep `params` as opaque `object`
("see template-specific schemas in the system prompt") but the system
prompt didn't actually include those schemas. The LLM had no signal
about which fields to fill in, so it called `search_users` with empty
`params={}`. The validator's "exactly one of …" message named the
field the LLM should have passed, which the LLM then misread as a
rejection of a parameter it never sent.

**Fix (commit 2026-05-03):** embed per-template `Params.model_json_schema()`
output into the system prompt under a `TOOL PARAMS SCHEMAS` section.
A regression test asserts the section is present and contains
`user_lookup` and `matter_lookup` schemas. See
`tests/unit/lina_supervisor/test_system_prompt.py`.

Also tightened the prompt's "CALLING TOOLS" section to spell out that
the validator's "exactly one of …" message means *send* the missing
identifier in the next call — not that the tool is broken.

**Surfaced in:** smoke test of conversation-history feature on
2026-05-03, branch `feat/ui-direction-d`.
