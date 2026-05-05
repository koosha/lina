# Design specs

Snapshot of the design specs that drove the original implementation —
useful as a record of why each subsystem looks the way it does, but not
maintained as the system evolves. The currently-correct view of the
system is in [`../architecture/data-schema.md`](../architecture/data-schema.md)
and the per-subsystem `src/` modules.

All five specs live under [`archive/`](./archive/):

- `2026-05-02-lina-supervisor-design.md` — LangGraph supervisor + tool routing
- `2026-05-02-lina-redshift-worker-design.md` — Subsystem C
- `2026-05-02-lina-opensearch-workers-design.md` — Subsystems A and B
- `2026-05-03-lina-aws-sandbox-design.md` — first AWS sandbox bring-up
- `2026-05-03-lina-ci-integration-tests-design.md` — CI environment
