# Plan: Inline citations in supervisor responses

## Problem

The Direction D wireframe and HANDOFF spec assume every fact in an
assistant message is grounded by an inline citation tag — `[1]`, `[2]`,
etc. — that maps to a card in the right-hand sources drawer.

Today the UI already renders `[N]` tokens as clickable citation buttons,
but the supervisor's `answer_text` rarely contains them. Users see a
prose answer on the left and a separate list of cards on the right with
no obvious connection between them.

Concrete example from the live demo (`https://lina-web-sooty.vercel.app`):

> Matter `matter_acme_v_beta` is an active commercial-litigation matter
> opened on 2023-08-12. The current approved budget is $480,000 …
>
> Sources used: 1 Matter & Spend (Matter Lookup), 2 Matter & Spend
> (Matter Spend Summary), 3 User Profiles (User Lookup)

The cards are correct. The prose is correct. But there's no `[1]` next
to "2023-08-12", no `[2]` next to "$480,000", etc. The reader has to
infer which fact came from which source.

## Why the supervisor isn't inserting citations

This lives entirely in `lina_supervisor.graph` — the synthesis-step
prompt that turns ResultPackets into prose. The current prompt asks for
"a clear, concise answer" but doesn't require inline citations or
specify their format.

When OpenAI gpt-5.2 sees the packets, it summarizes them as continuous
prose because that's what reads most naturally. Inline `[N]` markers
require explicit instruction, an example, and validation.

## Goal

After this work:

- Every factual claim in `answer_text` is followed by `[N]` where `N` is
  the 1-based index of the worker_packet it came from.
- The UI's existing citation rendering lights up — `[N]` tokens become
  clickable buttons that scroll-and-highlight the right-hand card.
- If a packet returned 0 results or errored, the synthesis explains
  the gap rather than fabricating a citation.

## Scope (what changes, where)

### 1. `src/lina_supervisor/synthesis_prompt.py` (or wherever the synthesis prompt lives)

Update the system/user message template the supervisor sends to OpenAI
during the synthesis node of the graph. New instructions:

> You are summarizing structured data from multiple internal systems
> for a legal professional. You will be given a numbered list of
> ResultPackets. For each factual claim in your answer, append the
> citation tag `[N]` where N is the 1-based packet index. Every
> sentence that states a fact must end with at least one `[N]`. Do
> not invent facts. If a packet is empty or errored, say so —
> e.g. "I don't have spend data for that matter [2]". Cite by the
> packet's position in the input list, not by source name.

Include a 1-shot example in the prompt so the model has a concrete
template to follow:

> **Input:**
> [1] redshift::matter_lookup → matter_id=matter_acme_v_beta,
>     status=Open, opened=2023-08-12
> [2] opensearch::user_lookup → user_id=user_jane_smith,
>     full_name="Jane Smith", department="Legal"
>
> **Output:**
> Matter `matter_acme_v_beta` is **Open**, opened on 2023-08-12 [1].
> The owner is **Jane Smith** in the Legal department [2].

### 2. Synthesis input shape

The input to the LLM today is a list of ResultPackets. The numbering
visible to the LLM must match what the UI uses. Two notes:

- The UI **dedupes packets by (source, result_type)** before assigning
  numbers (we collapse retry attempts). The LLM doesn't see this;
  it gets raw packets.
- Either teach the LLM to dedupe with the same rule (pass deduped
  numbering in the prompt), or skip dedup in the UI and trust the
  LLM's numbering.

**Recommendation:** dedupe in the supervisor *before* passing packets
to the LLM. Single source of truth, simpler UI. The supervisor already
does post-processing on packets, so this fits there. The UI's
`packetsToCitations` dedupe becomes redundant and can be removed.

### 3. Validation pass

After the LLM responds, parse the answer for `[N]` tokens. Validate:

- Every `[N]` references a real packet (1 ≤ N ≤ packets.length).
- Every non-empty/non-errored packet is referenced at least once.

If validation fails (LLM hallucinated a citation, or skipped one),
the supervisor can either:

- Log a warning and ship anyway (sandbox grade — keep moving).
- Loop back with a corrective prompt: "You skipped citations for
  packets 2, 4. Re-emit your answer with all citations included."

**Recommendation:** for the demo, log + ship. Wire the corrective
loop only if quality is visibly bad in user testing.

### 4. UI removals (cleanup)

Once the supervisor is the citation source of truth:

- `web/src/App.tsx` — remove the dedupe in `packetsToCitations`. Leave
  it as a 1:1 packet → citation map.
- The UI's citation hover/highlight already works; no UI changes
  needed beyond the removal.

## Sequencing

1. Land the supervisor prompt change with the new instructions and
   the 1-shot example. Ship to sandbox Lambda.
2. Verify in the live UI by running the same questions: every fact
   has a `[N]` next to it, clicking it lights up the right card.
3. Remove the UI-side dedupe.
4. (Optional, later) Add the validation+retry loop if quality slips.

## Out of scope

- Multi-citation tags like `[1, 3]` — the renderer handles a single
  `[N]` per token. If the supervisor needs to cite multiple packets
  for one claim, it should emit `[1] [3]` separately (the renderer
  already accepts that).
- Per-row citations (e.g. citing one row inside a multi-row packet
  separately). The packet, not the row, is the citation unit.
- A re-numbering scheme tied to the deduped UI cards (would force the
  LLM and the UI to agree on a non-trivial dedupe rule). Single-source
  numbering is simpler.

## Estimated effort

Half a day if the supervisor prompt is structured (just edit the
template). Up to a day if the synthesis flow needs refactoring to
emit deduped packets to the LLM. The UI side is a 5-line deletion.

## Open questions

- Do we want headers like "Sources used:" at the end of the prose, or
  is the right-hand drawer enough? **Recommendation:** drop the
  trailing source list — the drawer makes it redundant.
- Should errored packets get cited? Citing "[2]" on a "this lookup
  failed" sentence is honest but may feel awkward. **Recommendation:**
  cite them; the drawer card can show the result_type even on a 0-row
  outcome, and citing it makes the supervisor's reasoning auditable.
