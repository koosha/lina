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

## 2026-05-03 · P2 · open · `user_lookup` rejects `user_id` parameter

**Repro:** ask Lina "What is user_jane_smith's job title and department?"
through the live UI (or hit `/ask` directly with that query). The
supervisor calls `user_lookup` with `{"user_id": "user_jane_smith"}` and
the worker returns:

```
{
  "type": "InvalidParametersError",
  "message": "1 validation error for UserLookupParams\n  Value error, exactly one of user_id, email, employee_id is required"
}
```

The supervisor then re-prompts the user for one of `user_id`, `email`, or
`employee_id` — even though the request *did* include `user_id`.

**Likely cause:** the Pydantic validator for `UserLookupParams` in
`lina_users` is treating `user_id` as missing when only `user_id` is
passed. Probably a `model_validator` that checks `not any(...)` against
the wrong attribute names, or a mode-`before` validator running before
field assignment.

**Fix sketch:**
1. Reproduce locally:
   ```bash
   AWS_DEFAULT_REGION=us-east-1 .venv/bin/python -c \
     "from lina_users.templates.user_lookup import UserLookupParams; \
      print(UserLookupParams(user_id='user_jane_smith'))"
   ```
2. If it raises, the validator is the bug. Check the field names against
   what the validator references.
3. Add a unit test in `tests/unit/lina_users/templates/` that constructs
   each of the three valid single-field forms and asserts they succeed.
4. Add a parity integration test against OpenSearch (sandbox) once the
   validator passes.

**Workaround in the meantime:** the supervisor's reasoning still works
(it correctly resolves "her" → user_jane_smith from prior context — see
the conversation-history smoke test). Users just get a "please pass an
identifier" reply instead of the actual record.

**Surfaced in:** smoke test of conversation-history feature on
2026-05-03, branch `feat/ui-direction-d`.
