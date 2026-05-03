// Wireframe C — "Storefront / dashboard"
// Authenticated landing: chat hero + capabilities + how-it-works + trust strip.
// Two states: empty (landing) and answered (post-response).

function WireframeC({ width = 1100, height = 1380, state = "landing" }) {
  return (
    <div className="wf-frame" style={{ width, height, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <TopBar/>
      <div style={{ flex: 1, overflow: 'hidden', background: 'var(--paper)' }}>
        {state === "landing" ? <LandingHero/> : <AnsweredHero/>}

        {/* Capabilities */}
        <section style={{ padding: '40px 80px 32px' }}>
          <div className="wf-eyebrow" style={{ marginBottom: 8 }}>What Lina can do</div>
          <div className="wf-h" style={{ fontSize: 24, marginBottom: 22 }}>Three things, on tap.</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
            {CAPABILITIES.map((c, i) => (
              <div key={i} className="wf-box" style={{
                padding: 20,
                background: 'var(--paper)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
                minHeight: 170,
              }}>
                <div className="wf-eyebrow" style={{ color: 'var(--accent)' }}>{c.src}</div>
                <div className="wf-h" style={{ fontSize: 17 }}>{c.title}</div>
                <div style={{ color: 'var(--ink-3)', fontSize: 13.5, lineHeight: 1.5 }}>{c.body}</div>
              </div>
            ))}
          </div>
        </section>

        {/* How it works */}
        <section style={{ padding: '24px 80px 40px' }}>
          <div className="wf-eyebrow" style={{ marginBottom: 8 }}>How it works</div>
          <div className="wf-h" style={{ fontSize: 24, marginBottom: 6 }}>Connected to your firm's systems.</div>
          <div style={{ color: 'var(--ink-3)', fontSize: 14, marginBottom: 20, maxWidth: 640 }}>
            Lina answers by reading from three of your firm's data systems — only what your role permits. No information leaves your tenant.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
            {DATA_SOURCES.map((s, i) => (
              <div key={s.id} className="wf-box" style={{ padding: 18, minHeight: 120, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: 4, background: 'var(--accent)' }}/>
                  <div className="wf-h" style={{ fontSize: 16 }}>{s.name}</div>
                </div>
                <div style={{ color: 'var(--ink-3)', fontSize: 13, lineHeight: 1.5 }}>{s.body}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Trust strip */}
        <section style={{ padding: '20px 80px', borderTop: '1px solid var(--line-softer)', background: 'var(--paper-2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 22, flexWrap: 'wrap' }}>
            <span className="wf-eyebrow">Security</span>
            {TRUST_ITEMS.map((t, i) => (
              <span key={i} style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                color: 'var(--ink-2)', fontSize: 12.5,
              }}>
                <Ico.lock size={11}/> {t}
              </span>
            ))}
          </div>
        </section>

        <section style={{ padding: '14px 80px 22px' }}>
          <Disclaimer/>
        </section>
      </div>
    </div>
  );
}

function LandingHero() {
  return (
    <section style={{ padding: '56px 80px 24px', display: 'flex', flexDirection: 'column', gap: 22 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span className="wf-eyebrow">Welcome back, Jane</span>
        <div className="wf-display" style={{ fontSize: 38, maxWidth: 760 }}>
          Your practice, in plain English.
        </div>
        <div style={{ color: 'var(--ink-3)', fontSize: 16, maxWidth: 640 }}>
          Ask anything about your matters, the people in your firm, or your outside counsel.
        </div>
      </div>
      <div style={{ maxWidth: 820, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Composer showHint/>
        <SuggestionChips items={SAMPLE_QUESTIONS.slice(0, 4)} label="Try asking"/>
        <div style={{ marginTop: 6 }}><SourcesPill/></div>
      </div>
    </section>
  );
}

// Post-response state for C — the hero collapses, conversation appears below
// the (now sticky) composer. New chat button to start over.
function AnsweredHero() {
  return (
    <section style={{ padding: '32px 80px 24px', display: 'flex', flexDirection: 'column', gap: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div className="wf-eyebrow" style={{ marginBottom: 4 }}>Conversation</div>
          <div className="wf-h" style={{ fontSize: 18 }}>Walker spend on Acme v. Beta</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="wf-btn"><Ico.share/> Share</button>
          <button className="wf-btn wf-btn-primary"><Ico.plus/> New chat</button>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 22, maxWidth: 940 }}>
        <UserMsg text={SAMPLE_ANSWER.question}/>
        <AssistantMsg/>
      </div>

      <div style={{ maxWidth: 820, marginTop: 8 }}>
        <Composer compact placeholder="Ask a follow-up…"/>
      </div>
    </section>
  );
}

window.WireframeC = WireframeC;
