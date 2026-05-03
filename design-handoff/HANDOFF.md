# Lina — UI Implementation Handoff

This package describes the Lina chat UI for implementation. Build **Direction D** from the wireframes (`Lina Wireframes.html`, see artboards labeled `D · landing` and `D · after a response`).

> **Lina** = **L**egal **I**ntelligence & **N**avigation **A**ssistant.
> The full name appears once next to the logo in the top bar; everywhere else the product is called "Lina".

---

## 1. What's in this folder

| File | Purpose |
|---|---|
| `Lina Wireframes.html` | Open in a browser. Visual reference for both states of D. Also contains brief (artboard 00) and sample queries (artboard 01). |
| `wireframe-d.jsx` | Structural reference — layout, regions, behavior of D in both states. |
| `shared.jsx` | Component primitives (Composer, UserMsg, AssistantMsg, FeedbackBar, citation cards, SourcesPill, TopBar) and sample data. Lift the components, replace the mock data. |
| `styles.css` | Design tokens (color, spacing, type) and base classes. Port the tokens to your styling system. |
| `HANDOFF.md` | This file. |

---

## 2. Build target

**Direction D — Split-view with citations drawer.** Two states:

1. **Landing (empty)** — single centered column. Greeting, big composer with placeholder, four suggestion chips, a "Reading from Matter & Spend / User Profiles / Outside Counsel" pill, disclaimer pinned to bottom. No sidebar, no marketing chrome.
2. **Answered (post-response)** — chat fills the main column on the left; a persistent **Sources** drawer (340px) on the right. Drawer shows one card per citation referenced in the answer, plus a "Connected systems" footer. Composer becomes a sticky follow-up input at the bottom of the main column. **New chat** button in the header (no conversation history sidebar at this stage).

Both states share the same top bar: `[LINA]` badge + "Legal Intelligence & Navigation Assistant" tagline + Help link + user avatar. **No tenant name.**

---

## 3. Stack guidance

The wireframes are framework-agnostic JSX with inline styles. Translate to your target stack — likely React + Tailwind or React + CSS Modules. Confirm with the user before starting.

**Type stack (ship these, not system fallback):**
- Display + body: **Inter** (weights 400, 500, 600, 700)
- Monospace (timestamps, eyebrow labels, citation numbers, IDs only): **JetBrains Mono** (400, 500)
- Load via Google Fonts or self-host. Do not use Roboto, Arial, or system-ui as the primary face.

**Color tokens** (lift from `styles.css`):
```
--ink:        #14171a   /* primary text */
--ink-2:      #2f343a
--ink-3:      #5b6168   /* secondary text */
--ink-4:      #8a9098
--ink-5:      #b9bdc3
--paper:      #ffffff
--paper-2:    #f6f5f1   /* drawer / subtle bg */
--paper-3:    #ecebe5
--line-soft:  #d5d3cc
--line-softer:#e8e6df
--accent:     #1f3a4d   /* deep slate-blue — sober legal tone */
--highlight:  #f4eeda   /* parchment, used sparingly */
```

**Sizing rhythm:** body 14px / line-height 1.5. Display 22–38px, weight 600, letter-spacing -0.01 to -0.02em. Border radius 6–8px. Component padding multiples of 4px.

---

## 4. Components to lift verbatim

From `shared.jsx`, these can be ported component-for-component:

- `TopBar` — the LINA badge, tagline, help link, user avatar
- `Composer` — input with attach affordance, send button, optional hint row
- `SuggestionChips` — pill row, source the items from your real sample-queries source
- `SourcesPill` — "Reading from {three friendly source names}" inline pill
- `UserMsg` — user message bubble
- `AssistantMsg` — assistant message with paragraphs, inline `[1]` citation marks, `FeedbackBar`. In D, **disable inline source listings** (`withInlineSources={false}`) — citations live in the drawer.
- `FeedbackBar` — thumbs up/down, copy, regenerate, share
- Citation cards — see `DAnswered` in `wireframe-d.jsx`. Each card: number badge, source name (accent color), label, "View record" link.
- `Disclaimer` — uses the shared `DISCLAIMER` constant.

---

## 5. What to replace, not lift

These are mocked in the wireframes — replace with real data/integrations:

- `SAMPLE_QUESTIONS_FULL` array → load from your real `/docs/sample-queries.json` or backend endpoint. Use easy questions for chips and placeholder; harder cross-source ones in onboarding examples if you build that surface later.
- `SAMPLE_ANSWER` paragraphs and citations → wire to your supervisor + worker backend. Each `ResultPacket` returned by a worker becomes one citation card.
- Streaming "typing" dots — currently decorative. Replace with real streaming via your transport (SSE/WebSocket).
- "8s" timing label on the assistant message — fake. Replace with real elapsed-time on response.
- Thumbs up/down, copy, regenerate, share — non-functional. Wire to feedback API, clipboard, regeneration flow, and share-link generation.
- Help link — non-functional. Point at your help destination.

---

## 6. Source-name mapping — **keep server-side, never expose**

The UI shows **friendly names** for the three data systems. Internal worker names must never appear in user-facing strings, error messages, telemetry visible to users, URL params, or DOM text.

| UI label (visible) | Worker name (server-only) | What it covers |
|---|---|---|
| **Matter & Spend** | `lina-redshift` | Matters, budgets, invoices, billed hours, timekeeper rates |
| **User Profiles** | `lina-users` | People in the company — roles, departments, reporting lines |
| **Outside Counsel** | `lina-vendors` | Outside lawyers and firms — practice areas, jurisdictions, rates |

Citation cards display the **friendly name**. Backend logs and dev tools may use worker names; UI must not.

---

## 7. Copy strings (use exactly)

**Top-bar tagline (next to LINA badge):**
> Legal Intelligence & Navigation Assistant

**Disclaimer (bottom of every state):**
> Lina uses LLM to process queries and can make mistakes. Please review and validate results before relying on them.

**Landing greeting (D):**
> Welcome back, {firstName} — What can I help you with?

**Composer placeholder (default):**
> Try: How much has Walker billed on Acme v. Beta in 2024-Q4?
>
> (or pull a representative example from sample-queries.json on each session)

**Sources pill:**
> Reading from Matter & Spend, User Profiles, Outside Counsel

**Drawer header:** `Sources` · `{N} used`
**Drawer footer eyebrow:** `Connected systems`

---

## 8. Behavior contracts

- **Citation click** → highlight the matching card in the drawer. Smooth-scroll inside the drawer if needed; do not affect main column scroll.
- **Drawer card "View record" link** → open the underlying record in a new tab via the worker's record URL (returned in the `ResultPacket`).
- **New chat button** → clear conversation, return to landing state, focus composer.
- **Send button** disabled when composer is empty. Enter to send, Shift-Enter for newline.
- **Streaming**: show animated dots while the supervisor loops (≤ 8 worker calls per turn per the platform constraint). Replace dots with text as it streams in. Citations appear as soon as the corresponding `ResultPacket` arrives.
- **Empty answer / no results** → render assistant message with a graceful "I couldn't find that in your firm's data — try rephrasing or check that {source} contains the record." Always cite which source(s) were checked.
- **Permission-denied** → never show worker-level errors. Render "You don't have access to that information."

---

## 9. Do / Don't

**Do**
- Treat the wireframes as the structural and visual source of truth.
- Keep the sober, restrained tone — this is a legal tool, not a consumer chatbot.
- Maintain the citation discipline: every fact in an answer maps to a `ResultPacket`. No uncited claims.
- Use `accent` color sparingly — citation badges, primary actions, source-name labels.
- Render citation numbers in monospace, source names in display font.

**Don't**
- Don't introduce a conversation history sidebar yet — this is intentionally deferred.
- Don't show worker names (`lina-redshift`, etc.) anywhere visible.
- Don't show tenant / firm name in the top bar.
- Don't add emoji to UI strings.
- Don't add a tenant logo, marketing footer, or product tour overlay.
- Don't write freeform SQL or templates outside the platform's 14 read-only templates — this is a backend constraint, but ensure the UI doesn't suggest open-ended database queries to users.

---

## 10. Suggested implementation order

1. Token + type setup (port `styles.css` variables to your styling system).
2. Layout shells: `TopBar`, two-column split for D-Answered, single-column for D-Landing.
3. `Composer` + `SuggestionChips` + `SourcesPill` (visual only, no submit).
4. Wire backend: submit query, receive streaming text + result packets.
5. `UserMsg` + `AssistantMsg` with inline citation marks, `FeedbackBar`.
6. Citation drawer cards + click-to-highlight interaction.
7. `New chat` flow, follow-up composer, disclaimer placement.
8. Empty / error / permission-denied states.
9. Help link, share, regenerate, copy, feedback wiring.
10. Accessibility pass: keyboard nav for chips and citations, ARIA labels on icon buttons, focus management on `New chat`.

---

## 11. Questions to confirm before coding

- Target framework (React + Tailwind? Next.js? CSS modules?)
- Streaming transport (SSE / WebSocket / fetch ReadableStream?)
- Auth model — how does the UI obtain the user's role for permission-gated questions?
- Where do sample queries come from at runtime — bundled JSON or backend endpoint?
- Help link target.
- Telemetry — what feedback events should `FeedbackBar` emit?

---

*End of handoff. Open `Lina Wireframes.html` alongside this file while building.*
