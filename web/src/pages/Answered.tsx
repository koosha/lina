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
  initialQuestion: string;
  onSubmit: (text: string) => void;
  onNewChat: () => void;
}

export function Answered({ messages, initialQuestion, onSubmit, onNewChat }: AnsweredProps) {
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);

  // Aggregate all citations across answered assistant messages, in answer order.
  const allCitations: Citation[] = messages
    .filter((m) => m.role === "assistant" && !m.pending && m.citations)
    .flatMap((m) => m.citations ?? []);

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

  async function onShare() {
    try {
      await navigator.clipboard.writeText(window.location.href);
    } catch {
      /* ignore — sandbox demo */
    }
  }

  return (
    <div className="answered">
      <main className="answered__main">
        <div className="answered__header">
          <h2 className="answered__title" title={initialQuestion}>
            {initialQuestion}
          </h2>
          <div className="answered__actions">
            <button type="button" className="ghost-btn" onClick={onShare}>
              <Ico name="share" size={14} />
              <span>Share</span>
            </button>
            <button type="button" className="ghost-btn ghost-btn--accent" onClick={onNewChat}>
              <Ico name="plus" size={14} />
              <span>New chat</span>
            </button>
          </div>
        </div>

        <div className="answered__thread" ref={threadRef}>
          {messages.map((m) =>
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
