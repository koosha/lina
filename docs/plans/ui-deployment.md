# Lina UI Deployment Plan — Sandbox

> **Goal:** ship the Direction D UI to a URL 1–2 trusted users can open in a
> browser and have it talk to the existing v1.1 sandbox API.
>
> **Scope:** demo-grade. No real-user auth, no multi-tenant isolation, no
> rate-limited per-user keys. The sandbox API key ships in the JS bundle
> behind a hardcoded passphrase gate — together that's enough friction for a
> shared demo link, but anyone with DevTools can still read the key.
>
> **Branch:** `feat/ui-direction-d`

## What's already done on this branch

- `web/` — Vite + React + TypeScript app, no CSS framework, design tokens
  ported from `design-handoff/styles.css`. Direction D Landing + Answered
  states implemented per `design-handoff/HANDOFF.md`. Verified in browser
  with Playwright (landing, error path, mocked-success, citation
  highlighting, passphrase gate, mobile).
- `infra/tofu/api_gateway.tf` — CORS block added so a browser can call
  `POST /ask`.
- `infra/tofu/variables.tf` — `cors_allowed_origins` variable, defaults to
  `["*"]`.

## Architecture (what runs where)

```
┌─ Browser (1–2 users) ─────────────────────────────────────────────┐
│                                                                   │
│  [optional passphrase gate]                                       │
│         │                                                         │
│         ▼                                                         │
│  Static SPA  ──POST /ask + x-api-key──►  API Gateway HTTP API     │
│  (S3 + CloudFront                       (CORS allows browser     │
│   or Vercel/Netlify)                     origin; authorizer       │
│                                          Lambda checks key)       │
│                                                  │                │
│                                                  ▼                │
│                                          Supervisor Lambda        │
│                                          → Redshift / OpenSearch  │
└───────────────────────────────────────────────────────────────────┘
```

The frontend is fully static. The API key sits in the bundle (`VITE_*`
inlining). The passphrase gate is client-side only — it does **not**
protect the API endpoint, just the UI surface.

## The simplest path (recommended): Vercel + tofu apply

Five steps, ~20 minutes. No new AWS infrastructure.

### Step 1 — Apply the CORS change

The API currently has no CORS headers; a browser fetch from any origin will
fail at preflight. The change is already staged on this branch.

```bash
cd infra/tofu
TF_VAR_openai_api_key="$(aws secretsmanager get-secret-value \
  --secret-id lina/sandbox/openai-api-key \
  --query SecretString --output text \
  --profile lina-sandbox | jq -r .api_key)" \
  /tmp/tofu apply
```

Expected plan diff: one in-place update on `aws_apigatewayv2_api.this`
adding the `cors_configuration` block. No data plane changes.

> **Tighten later:** once the UI has a permanent host, set
> `TF_VAR_cors_allowed_origins='["https://<host>"]'` and re-apply.

### Step 2 — Get the sandbox API key

```bash
aws secretsmanager get-secret-value \
  --secret-id lina/sandbox/api-key \
  --query SecretString --output text \
  --profile lina-sandbox | jq -r .api_key
```

Copy this value — it's what users implicitly authenticate with.

### Step 3 — Configure and build the web app

```bash
cd web
cp .env.example .env.local
# Fill in:
#   VITE_LINA_API_BASE=https://kfrbjzy4l7.execute-api.us-east-1.amazonaws.com
#   VITE_LINA_API_KEY=<value from step 2>
#   VITE_LINA_PASSPHRASE=<pick a memorable phrase you'll share with the 1–2 users>
npm install
npm run build
```

Verify locally first:

```bash
npm run preview
# open http://127.0.0.1:5173 — gate, ask a real question, see citations
```

### Step 4 — Deploy to Vercel (or any static host)

```bash
# Once, globally:
npm i -g vercel

cd web
vercel --prod   # follow prompts; pick "static" / no framework override needed
# Vercel auto-detects Vite. Output dir: dist
```

Vercel returns a URL like `https://lina-web-<hash>.vercel.app`. Share that
URL + the passphrase with your 1–2 users.

> **Why Vercel for sandbox:** zero new AWS surface, free tier covers this
> traffic comfortably, atomic rollbacks, automatic HTTPS, and you don't
> need to wire CloudFront. If you'd rather stay all-AWS, see Alternative A
> below.

### Step 5 — Restrict CORS to the deployed origin

Once you know the Vercel host:

```bash
cd infra/tofu
TF_VAR_cors_allowed_origins='["https://lina-web-<hash>.vercel.app"]' \
TF_VAR_openai_api_key="…" \
  /tmp/tofu apply
```

This is optional but tightens the blast radius from "any origin" to "your
demo".

## Alternative A — All-AWS (S3 + CloudFront)

Heavier, but no third-party hosting. Adds ~10 minutes.

1. Create an S3 bucket: `lina-web-sandbox` (block public access on, default).
2. Create a CloudFront distribution with the bucket as origin via Origin
   Access Control. Default root object: `index.html`. Custom error 403/404
   → `/index.html` 200 (so SPA routing works if we ever add it).
3. `aws s3 sync web/dist/ s3://lina-web-sandbox/ --delete --profile lina-sandbox`
4. `aws cloudfront create-invalidation --distribution-id <id> --paths "/*"`
5. Set `TF_VAR_cors_allowed_origins='["https://<dxxxx>.cloudfront.net"]'`
   and re-apply.

If we go this route I'll add `infra/tofu/web_hosting.tf` so it's
reproducible — but for 1–2 demo users it's overkill.

## Alternative B — Don't deploy, just `npm run dev`

For a single demo session over screenshare:

```bash
cd web
npm run dev
# Localhost served at http://127.0.0.1:5173 — no third-party host needed.
```

CORS step still required (the browser hits API Gateway from `localhost`).
The `cors_allowed_origins=["*"]` default covers this.

## Security posture (be honest with stakeholders)

What this protects against:

- Random crawlers / casual visitors stumbling onto the demo URL.
- Accidentally exposed-link sharing — passphrase friction stops "I clicked
  the link in Slack" probes.

What this does **not** protect against:

- Anyone who pulls the JS bundle from DevTools sees the API key and can
  POST `/ask` directly without the passphrase. The 50/25 RPS throttle on
  the API Gateway stage limits damage but doesn't prevent reads.
- The OpenAI bill: `/ask` calls the OpenAI API. Sustained abuse would
  show up on the AWS Cost Explorer the next day.

If/when this graduates beyond 1–2 trusted demo users, the hardening list:

1. Move the API key out of the bundle: tiny proxy (Vercel function or
   second Lambda) that adds the header server-side. The proxy can be
   gated by a real session cookie.
2. Real auth (Cognito or third-party IdP) — the Subsystem A `CallerContext`
   already expects a `user_id`, so this is largely a frontend change plus
   a new authorizer that validates a JWT.
3. Per-user rate limits on the API.
4. Per-user OpenAI cost ceilings (telemetry already logs `worker_call_count`
   and trace IDs — can be turned into per-user quotas).

## Cleanup / rollback

If anything goes wrong:

- Roll the deploy back: Vercel → Deployments → Promote previous build.
  S3 → re-sync the prior `dist/` snapshot.
- Roll the API back: `git revert <commit>` on `infra/tofu/api_gateway.tf`,
  apply. CORS removal is a single in-place update.
- Kill the demo entirely: rotate the sandbox API key
  (`aws secretsmanager update-secret --secret-id lina/sandbox/api-key …`).
  Existing bundles stop working immediately because the authorizer Lambda
  re-fetches on cold start.

## Open items I'm flagging for you

1. **Pick a host** — Vercel (simpler) vs. AWS S3+CloudFront (all-AWS).
2. **Pick a passphrase** — needs to be memorable enough to type but not
   guessable. Suggestion: a 4-word random phrase, e.g. `oak-river-trial-93`.
3. **Confirm the demo `user_id`** — currently defaults to
   `user_jane_smith` (seeded). If you want each user to "be" different
   people for the demo, we can prompt for a name on the gate and map it
   to a seeded ID.
4. **Should I run `tofu apply` for the CORS change now**, or wait until
   you're ready to deploy the UI?
