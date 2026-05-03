# Lina Web — Direction D

Demo-grade chat surface for the Lina sandbox. React + TypeScript + Vite. Plain
CSS using design tokens ported from `design-handoff/styles.css`. No CSS
framework.

## Quick start

```bash
cd web
cp .env.example .env.local
# Edit .env.local — minimum required:
#   VITE_LINA_API_BASE = https://<api-id>.execute-api.us-east-1.amazonaws.com
#   VITE_LINA_API_KEY  = <sandbox key from Secrets Manager>
npm install
npm run dev
# open http://127.0.0.1:5173
```

## Build

```bash
npm run build         # → dist/
npm run preview       # serve dist/ locally on :5173
npm run typecheck
```

## Layout

```
web/
├── index.html
├── src/
│   ├── main.tsx                 ← entrypoint
│   ├── App.tsx                  ← chat state, dispatches /ask, gate switch
│   ├── styles/
│   │   ├── tokens.css           ← :root design tokens
│   │   └── global.css
│   ├── lib/
│   │   ├── api.ts               ← POST /ask client
│   │   ├── sources.ts           ← source-name mapping (worker → friendly)
│   │   ├── sampleQueries.ts     ← bundled docs/sample-queries.json
│   │   └── types.ts
│   ├── components/              ← TopBar, Composer, Chips, Pill, Disclaimer,
│   │                              Messages, CitationsDrawer, Ico
│   └── pages/
│       ├── Landing.tsx          ← empty state (centered greeting + composer)
│       ├── Answered.tsx         ← split view (thread + citations drawer)
│       └── PassphraseGate.tsx   ← optional landing-page passphrase gate
```

## Source-name mapping

Worker IDs and `source_engine` values **never** reach the UI. Translation
happens in [`src/lib/sources.ts`](src/lib/sources.ts):

| `source_engine` from API                    | UI label             |
| ------------------------------------------- | -------------------- |
| `redshift`                                  | **Matter & Spend**   |
| `opensearch` + user/manager/department type | **User Profiles**    |
| `opensearch` + lawyer/vendor type           | **Outside Counsel**  |

If a new `result_type` is added on the worker side, extend the
`USER_RESULT_TYPES` / `VENDOR_RESULT_TYPES` sets to keep disambiguation
reliable.

## Environment variables

All variables are inlined at build time by Vite (`import.meta.env`) — they
ship in the bundle. The API key is therefore visible in DevTools to anyone
who loads the site.

| Variable                  | Required | Notes                                                   |
| ------------------------- | -------- | ------------------------------------------------------- |
| `VITE_LINA_API_BASE`      | Yes      | API Gateway endpoint, no trailing slash.                |
| `VITE_LINA_API_KEY`       | Yes      | Sandbox key. Rotate if the bundle leaks broadly.        |
| `VITE_LINA_USER_ID`       | No       | Defaults to `user_jane_smith`. Should match seed data.  |
| `VITE_LINA_PASSPHRASE`    | No       | Hardcoded gate. Empty → no gate.                        |
| `VITE_LINA_FIRST_NAME`    | No       | First name in the landing greeting.                     |

## Deployment

See [`docs/plans/ui-deployment.md`](../docs/plans/ui-deployment.md) for the
end-to-end plan (CORS update on the API, S3 + CloudFront static hosting,
passphrase gate setup, and rollback).
