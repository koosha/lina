// Lina wireframe — shared primitives & sample data (clean, professional)
// User-facing names: "Matter & Spend", "User Profiles", "Outside Counsel".
// No mention of redshift / opensearch in any user-visible string.

// Real questions from /docs/sample-queries.json — paraphrased lightly so
// they read like a lawyer would type, not like a test fixture.
const SAMPLE_QUESTIONS_FULL = [
{ id: "rs-matter-summary", text: "What's the practice area, status, open date, and budget for matter Acme v. Beta?", sources: ["matters"], difficulty: "easy" },
{ id: "rs-spend-summary", text: "Show total approved spend, invoice count, and budget utilization for Acme v. Beta in 2024-Q4.", sources: ["matters"], difficulty: "easy" },
{ id: "users-lookup-by-id", text: "What is Jane Smith's job title, department, and email?", sources: ["people"], difficulty: "easy" },
{ id: "users-manager-chain", text: "Walk the reporting chain upward from Alex Lee. Who is their manager, and their manager's manager?", sources: ["people"], difficulty: "medium" },
{ id: "vendors-find-walker-partner", text: "Show me the partner-level lawyers at Walker & Associates, including bar admissions and standard hourly rate.", sources: ["counsel"], difficulty: "easy" },
{ id: "vendors-privacy-experts", text: "Which outside counsel lawyers in our network specialize in privacy or data-protection work?", sources: ["counsel"], difficulty: "medium" },
{ id: "matter-with-owner-profile", text: "Look up Acme v. Beta — name, status, budget, plus the owner's full name, email, and department.", sources: ["matters", "people"], difficulty: "easy" },
{ id: "vendor-spend-with-partner", text: "How much has Walker billed on Acme v. Beta in 2024-Q4, and who's the senior partner from that firm leading the engagement?", sources: ["matters", "counsel"], difficulty: "medium" },
{ id: "rate-variance-with-rates", text: "On Acme v. Beta last quarter, list each Walker timekeeper's billed hours, billed rate, and standard rate. Flag anyone billing >5% above standard.", sources: ["matters", "counsel"], difficulty: "hard" },
{ id: "top-spenders-with-owners", text: "Which three open matters have the highest total approved spend? For each: name, total spend, and the matter owner.", sources: ["matters", "people"], difficulty: "hard" }];


const SAMPLE_QUESTIONS = SAMPLE_QUESTIONS_FULL.map((q) => q.text);

// Greyed-out placeholder — pulled from the canonical sample list.
const PLACEHOLDER_QUESTION =
"Try: How much has Walker billed on Acme v. Beta in 2024-Q4?";

// Industry-standard disclaimer wording (matches Anthropic / OpenAI patterns).
const DISCLAIMER =
"Lina can make mistakes. Please review and validate results before relying on them.";

// User-facing source names. Internal worker mapping kept in a comment for the
// coding agent — the UI must NEVER show "lina-redshift" or "OpenSearch".
//   "Matter & Spend"   → lina-redshift   (Subsystem C)
//   "User Profiles"    → lina-users      (Subsystem A)
//   "Outside Counsel"  → lina-vendors    (Subsystem B)
const DATA_SOURCES = [
{ id: "matters", name: "Matter & Spend", body: "Matters, budgets, invoices, billed hours, timekeeper rates." },
{ id: "people", name: "User Profiles", body: "People in your company — roles, departments, reporting lines." },
{ id: "counsel", name: "Outside Counsel", body: "Outside lawyers and firms — practice areas, jurisdictions, rates." }];


// "What Lina can do" capability cards.
const CAPABILITIES = [
{
  title: "Analyze matters and spend",
  body: "Spend summaries, budget utilization, vendor and timekeeper rate analysis, invoices, and line items.",
  src: "Matter & Spend"
},
{
  title: "Find people inside your company",
  body: "Look up colleagues, search by role or department, walk reporting lines.",
  src: "User Profiles"
},
{
  title: "Find outside counsel",
  body: "Search vendor lawyers and firms by practice area, jurisdiction, partner level, or rate.",
  src: "Outside Counsel"
}];


// Trust strip — derived from real platform constraints, in user-readable terms.
const TRUST_ITEMS = [
"Read-only access",
"Role-based permissions",
"Every answer is cited",
"No model training on your data"];


// Mock answer used in the "post-response" states.
const SAMPLE_ANSWER = {
  question: "How much has Walker billed on Acme v. Beta in 2024-Q4, and who's the senior partner leading the engagement?",
  paragraphs: [
  "Walker & Associates billed $487,250 on Acme v. Beta in 2024-Q4 across 3 timekeepers — 142.5 partner hours, 218 associate hours, and 64 paralegal hours. That's an 18% increase over Q3.",
  "The senior partner leading the engagement is Marcus Walker (Partner, NY Bar). His standard rate is $1,250/hr and he billed at standard. About 62% of the quarter's spend was on document review and diligence."],

  citations: [
  { n: 1, source: "Matter & Spend", label: "Matter Acme v. Beta · 2024-Q4 spend summary" },
  { n: 2, source: "Outside Counsel", label: "Walker & Associates · partner roster" },
  { n: 3, source: "Matter & Spend", label: "Walker timekeeper rate analysis" }]

};

// Tiny inline icons.
const Ico = {
  send: ({ size = 14 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <path d="M2 7 L12 2 L9 7 L12 12 Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" fill="none" />
    </svg>,

  plus: ({ size = 14 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14"><path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>,

  thumbUp: ({ size = 13 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <path d="M3 7v5h7l2-5V5H8l1-3-1-1L5 5v2H3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>,

  thumbDown: ({ size = 13 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <path d="M3 7V2h7l2 5v2H8l1 3-1 1-3-4V7H3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>,

  copy: ({ size = 13 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <rect x="4" y="4" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <path d="M2 10V3a1 1 0 0 1 1-1h7" stroke="currentColor" strokeWidth="1.3" />
    </svg>,

  redo: ({ size = 13 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <path d="M2 7a5 5 0 0 1 9-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" fill="none" />
      <path d="M11 1v3h-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" fill="none" />
    </svg>,

  share: ({ size = 13 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <circle cx="3.5" cy="7" r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="10.5" cy="3.5" r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <circle cx="10.5" cy="10.5" r="1.5" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5 6L9 4M5 8L9 10" stroke="currentColor" strokeWidth="1.3" />
    </svg>,

  lock: ({ size = 12 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <rect x="3" y="6" width="8" height="6" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <path d="M5 6V4a2 2 0 0 1 4 0v2" stroke="currentColor" strokeWidth="1.3" />
    </svg>,

  chev: ({ size = 12, dir = "down" }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none" style={{ transform: dir === "up" ? "rotate(180deg)" : "" }}>
      <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>,

  ext: ({ size = 11 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <path d="M5 2h7v7M12 2L6 8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M11 8v4H2V3h4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>,

  search: ({ size = 13 }) =>
  <svg width={size} height={size} viewBox="0 0 14 14" fill="none">
      <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.3" />
      <path d="M9 9l3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>

};

// Top app bar.
function TopBar({ user = "JS" }) {
  return (
    <div style={{
      height: 56,
      borderBottom: '1px solid var(--line-softer)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 24px',
      gap: 12,
      background: 'var(--paper)',
      flexShrink: 0
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          height: 26, borderRadius: 6,
          background: 'var(--accent)',
          color: 'var(--paper)',
          display: 'grid', placeItems: 'center',
          fontSize: 11,
          letterSpacing: '0.06em',
          fontFamily: 'var(--font-display)', fontWeight: 900,
          padding: '0 8px',
        }}>LINA</div>
        <span style={{ color: 'var(--ink-3)', fontSize: 13 }}>Legal Intelligence &amp; Navigation Assistant</span>
      </div>
      <div style={{ flex: 1 }} />
      <span style={{ color: 'var(--ink-3)', fontSize: 13, cursor: 'pointer' }}>Help</span>
      <div className="wf-dot" title="user">{user}</div>
    </div>);

}

// Composer.
function Composer({ placeholder = PLACEHOLDER_QUESTION, compact = false, value = "", showHint = false }) {
  return (
    <div className="wf-box" style={{
      background: 'var(--paper)',
      padding: compact ? '12px 14px' : '16px 18px',
      display: 'flex',
      alignItems: 'flex-end',
      gap: 12,
      minHeight: compact ? 56 : 100,
      boxShadow: '0 1px 2px rgba(20,23,26,0.04)'
    }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
        {value ?
        <span style={{ color: 'var(--ink)', fontSize: compact ? 14 : 15 }}>
            {value}<span className="wf-caret" />
          </span> :

        <span style={{ color: 'var(--ink-4)', fontSize: compact ? 14 : 15 }}>
            {placeholder}<span className="wf-caret" />
          </span>
        }
        {showHint && !compact &&
        <span className="wf-mono" style={{ color: 'var(--ink-4)' }}>
            ⏎ to send · shift+⏎ for new line
          </span>
        }
      </div>
      <button className="wf-btn wf-btn-primary" style={{ alignSelf: 'flex-end' }}>
        <Ico.send /> Send
      </button>
    </div>);

}

// Suggestion chips.
function SuggestionChips({ items = SAMPLE_QUESTIONS.slice(0, 4), label = "Try asking" }) {
  return (
    <div>
      {label && <div className="wf-eyebrow" style={{ marginBottom: 10 }}>{label}</div>}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {items.map((q, i) =>
        <span key={i} className="wf-chip">{q}</span>
        )}
      </div>
    </div>);

}

function Disclaimer() {
  return <div className="wf-disclaimer">{DISCLAIMER}</div>;
}

// "Connected to" pill — shows the three user-facing source names.
function SourcesPill() {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 10,
      border: '1px solid var(--line-softer)',
      borderRadius: 999,
      padding: '5px 12px',
      fontSize: 11.5,
      color: 'var(--ink-3)'
    }}>
      <Ico.lock size={11} />
      <span style={{ fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Connected:</span>
      {DATA_SOURCES.map((s, i) =>
      <React.Fragment key={s.id}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--accent)' }} />
            {s.name}
          </span>
          {i < DATA_SOURCES.length - 1 && <span style={{ color: 'var(--ink-5)' }}>·</span>}
        </React.Fragment>
      )}
    </div>);

}

// User message bubble.
function UserMsg({ text, avatar = "JS" }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <div className="wf-dot">{avatar}</div>
      <div style={{
        padding: '10px 14px',
        background: 'var(--paper-2)',
        border: '1px solid var(--line-softer)',
        borderRadius: 8,
        maxWidth: '80%',
        fontSize: 14,
        color: 'var(--ink)'
      }}>{text}</div>
    </div>);

}

// Assistant answer block — paragraphs with inline citation refs + actions.
function AssistantMsg({ answer = SAMPLE_ANSWER, withCitations = true, withInlineSources = true }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
      <div className="wf-dot" style={{
        background: 'var(--accent)', color: 'var(--paper)', borderColor: 'var(--accent)'
      }}>L</div>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0 }}>
        <div style={{ fontSize: 14.5, lineHeight: 1.65, color: 'var(--ink)' }}>
          {answer.paragraphs.map((p, i) =>
          <p key={i} style={{ margin: i === 0 ? 0 : '10px 0 0' }}>
              {p}
              {withCitations && <span className="wf-cite">{Math.min(i + 1, answer.citations.length)}</span>}
            </p>
          )}
        </div>
        {withInlineSources &&
        <div style={{
          display: 'flex', flexDirection: 'column', gap: 6,
          padding: '10px 12px',
          border: '1px solid var(--line-softer)',
          borderRadius: 6,
          background: 'var(--paper-2)'
        }}>
            <div className="wf-eyebrow">Sources</div>
            {answer.citations.map((c) =>
          <div key={c.n} style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 12.5 }}>
                <span className="wf-cite">{c.n}</span>
                <span style={{ color: 'var(--accent)', fontWeight: 500 }}>{c.source}</span>
                <span style={{ color: 'var(--ink-3)' }}>· {c.label}</span>
                <span style={{ flex: 1 }} />
                <span style={{ color: 'var(--ink-4)', display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
                  View <Ico.ext />
                </span>
              </div>
          )}
          </div>
        }
        <FeedbackBar />
      </div>
    </div>);

}

function FeedbackBar() {
  return (
    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      <button className="wf-thumb" title="Helpful"><Ico.thumbUp /></button>
      <button className="wf-thumb" title="Not helpful"><Ico.thumbDown /></button>
      <button className="wf-thumb" title="Copy"><Ico.copy /></button>
      <button className="wf-thumb" title="Regenerate"><Ico.redo /></button>
      <button className="wf-thumb" title="Share"><Ico.share /></button>
    </div>);

}

Object.assign(window, {
  SAMPLE_QUESTIONS, SAMPLE_QUESTIONS_FULL, PLACEHOLDER_QUESTION, DISCLAIMER, SAMPLE_ANSWER,
  CAPABILITIES, DATA_SOURCES, TRUST_ITEMS,
  Ico, TopBar, Composer, SuggestionChips, Disclaimer, SourcesPill,
  UserMsg, AssistantMsg, FeedbackBar
});