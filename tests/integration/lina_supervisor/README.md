# Supervisor integration tests

These tests exercise the full supervisor flow against a real OpenAI API. They
use VCR cassettes to replay recorded interactions, so they pass without
burning API credits or requiring an active key.

## Recording cassettes (one-time setup)

```bash
export OPENAI_API_KEY=sk-...
.venv/bin/pytest tests/integration/lina_supervisor/ -m integration --vcr-record=once
```

This creates YAML cassette files in `cassettes/`. Commit them.

## Replaying

```bash
.venv/bin/pytest tests/integration/lina_supervisor/ -m integration
```

When a cassette exists, the test replays without any API key. When neither
cassette nor key is present, the test skips cleanly (the conftest hook adds
a `pytest.mark.skip` marker before the test runs).

## Skip logic

`conftest.py` checks for `cassettes/<test_name>.yaml`. If absent and
`OPENAI_API_KEY` is not set, the test is skipped with a descriptive reason.
This avoids the `CannotOverwriteExistingCassetteException` that pytest-vcr
would otherwise raise in `record_mode="none"`.

## Security

Cassettes have `Authorization` and `OpenAI-Organization` headers redacted via
the conftest `vcr_config` fixture. Verify any new cassette before committing —
secrets in committed YAML are a leak.

## Workers are mocked

The supervisor wiring in these tests uses a real OpenAI client (replayed or
live) but mocks `RedshiftWorker`, `UserSearchWorker`, and
`VendorSearchWorker`. This keeps the cassette focused on the LLM routing
behavior; backend smoke tests live under `tests/integration/test_redshift_*`,
`tests/integration/lina_users/`, and `tests/integration/lina_vendors/`.
