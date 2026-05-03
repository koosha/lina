# Known Issues

Append-only log. Newest at the top. Each entry: severity · status · short
description · repro · likely cause · fix sketch.

Severities:
- **P1** — blocks a core demo path or could lose/corrupt data.
- **P2** — degrades the demo (wrong answer, ugly fallback) but workable.
- **P3** — cosmetic or rare edge case.

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
