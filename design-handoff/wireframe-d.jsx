// Wireframe D — "Split-view with live citations"
// Two states: empty (landing — single column centered) and
// answered (chat left + persistent citation drawer right).

function WireframeD({ width = 1100, height = 760, state = "answered" }) {
  return (
    <div className="wf-frame" style={{ width, height, display: 'flex', flexDirection: 'column' }}>
      <TopBar/>
      {state === "landing" ? <DLanding/> : <DAnswered/>}
    </div>
  );
}

function DLanding() {
  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px 80px',
      gap: 28,
      background: 'var(--paper)',
    }}>
      <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 8 }}>
        <span className="wf-eyebrow">Welcome back, Jane</span>
        <div className="wf-display" style={{ fontSize: 36 }}>What can I help you with?</div>
      </div>
      <div style={{ width: '100%', maxWidth: 720, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <Composer showHint/>
        <SuggestionChips items={SAMPLE_QUESTIONS.slice(0, 4)}/>
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 6 }}><SourcesPill/></div>
      </div>
      <div style={{ position: 'absolute', bottom: 16, left: 0, right: 0 }}><Disclaimer/></div>
    </div>
  );
}

function DAnswered() {
  return (
    <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
      {/* Chat column */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        borderRight: '1px solid var(--line-softer)',
      }}>
        <div style={{
          padding: '14px 28px',
          borderBottom: '1px solid var(--line-softer)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div className="wf-h" style={{ fontSize: 15 }}>Walker spend on Acme v. Beta</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="wf-btn"><Ico.share/> Share</button>
            <button className="wf-btn wf-btn-primary"><Ico.plus/> New chat</button>
          </div>
        </div>

        <div style={{
          flex: 1,
          padding: '24px 28px',
          display: 'flex',
          flexDirection: 'column',
          gap: 22,
          overflow: 'hidden',
        }}>
          <UserMsg text={SAMPLE_ANSWER.question}/>
          {/* No inline-source block — citations live in right drawer instead */}
          <AssistantMsg withInlineSources={false}/>
        </div>

        <div style={{ padding: '14px 28px 12px', borderTop: '1px solid var(--line-softer)' }}>
          <Composer compact placeholder="Ask a follow-up…"/>
          <div style={{ marginTop: 8 }}><Disclaimer/></div>
        </div>
      </main>

      {/* Citations drawer */}
      <aside style={{
        width: 340,
        background: 'var(--paper-2)',
        padding: 20,
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="wf-h" style={{ fontSize: 15 }}>Sources</div>
          <span className="wf-mono" style={{ color: 'var(--ink-3)' }}>{SAMPLE_ANSWER.citations.length} used</span>
        </div>
        <div style={{ color: 'var(--ink-3)', fontSize: 12.5, lineHeight: 1.5 }}>
          Every fact in the answer maps back to a record in one of your firm's systems. Click a citation in the answer to highlight it here.
        </div>
        {SAMPLE_ANSWER.citations.map(c => (
          <div key={c.n} className="wf-box" style={{
            padding: 12,
            background: 'var(--paper)',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span className="wf-cite">{c.n}</span>
              <span style={{ color: 'var(--accent)', fontSize: 12.5, fontWeight: 500 }}>{c.source}</span>
            </div>
            <div style={{ fontSize: 13, color: 'var(--ink)' }}>{c.label}</div>
            <div style={{ color: 'var(--ink-4)', fontSize: 11.5, display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
              View record <Ico.ext/>
            </div>
          </div>
        ))}
        <div style={{ flex: 1 }}/>
        <div style={{ borderTop: '1px solid var(--line-softer)', paddingTop: 12 }}>
          <div className="wf-eyebrow" style={{ marginBottom: 8 }}>Connected systems</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {DATA_SOURCES.map(s => (
              <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ink-2)' }}>
                <span style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--accent)' }}/>
                {s.name}
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

window.WireframeD = WireframeD;
