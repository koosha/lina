import { useEffect, useRef, useState } from "react";
import { Composer } from "../components/Composer";
import { Disclaimer } from "../components/Disclaimer";
import { Ico } from "../components/Ico";
import { AssistantMsg, UserMsg } from "../components/Messages";
import { CitationsDrawer } from "../components/CitationsDrawer";
import type { Citation, UiMessage } from "../lib/types";
import "./Answered.css";

interface AnsweredProps {
  messages: UiMessage[];
  onSubmit: (text: string) => void;
  onNewChat: () => void;
}

export function Answered({ messages, onSubmit, onNewChat }: AnsweredProps) {
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);

  // Renumber citations sequentially across the whole conversation. Each
  // message's `packetsToCitations` numbers them 1..N within that message;
  // when we flatten into the drawer we want a single 1..M sequence so two
  // assistant messages with one citation each surface as cards 1 and 2,
  // not two cards both labeled 1.
  const renumbered = renumberCitationsAcrossMessages(messages);
  const allCitations: Citation[] = renumbered.flatMap(
    (m) => (m.role === "assistant" && !m.pending && m.citations ? m.citations : []),
  );

  const isPending = messages.some((m) => m.pending);

  // Auto-scroll thread to bottom on new messages.
  useEffect(() => {
    const el = threadRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, isPending]);

  function onCitationClick(index: number) {
    setHighlighted(index);
    const target = document.getElementById(`citation-${index}`);
    target?.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => setHighlighted((h) => (h === index ? null : h)), 1800);
  }

  return (
    <div className="answered">
      <main className="answered__main">
        <div className="answered__header">
          <button type="button" className="ghost-btn ghost-btn--accent" onClick={onNewChat}>
            <Ico name="plus" size={14} />
            <span>New chat</span>
          </button>
        </div>

        <div className="answered__thread" ref={threadRef}>
          {renumbered.map((m) =>
            m.role === "user" ? (
              <UserMsg key={m.id} text={m.text} />
            ) : (
              <AssistantMsg key={m.id} message={m} onCitationClick={onCitationClick} />
            ),
          )}
        </div>

        <div className="answered__composer">
          <Composer
            variant="compact"
            placeholder="Ask a follow-up…"
            onSubmit={onSubmit}
            pending={isPending}
          />
          <Disclaimer className="answered__disclaimer" />
        </div>
      </main>

      <CitationsDrawer citations={allCitations} highlightedIndex={highlighted} />
    </div>
  );
}

function renumberCitationsAcrossMessages(messages: UiMessage[]): UiMessage[] {
  let running = 0;
  return messages.map((m) => {
    if (m.role !== "assistant" || !m.citations || m.citations.length === 0) return m;
    const next: Citation[] = m.citations.map((c) => {
      running += 1;
      return { ...c, index: running };
    });
    return { ...m, citations: next };
  });
}
