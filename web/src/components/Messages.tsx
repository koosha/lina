import { useState } from "react";
import { Ico } from "./Ico";
import type { Citation, UiMessage } from "../lib/types";
import "./Messages.css";

interface UserMsgProps {
  text: string;
}

export function UserMsg({ text }: UserMsgProps) {
  return (
    <div className="msg msg--user">
      <div className="msg__bubble">{text}</div>
    </div>
  );
}

interface AssistantMsgProps {
  message: UiMessage;
  onCitationClick?: (index: number) => void;
}

export function AssistantMsg({ message, onCitationClick }: AssistantMsgProps) {
  if (message.pending) {
    return (
      <div className="msg msg--assistant">
        <div className="msg__pending" aria-live="polite">
          <span className="msg__dot" />
          <span className="msg__dot" />
          <span className="msg__dot" />
          <span className="msg__pending-label">Looking across the connected systems…</span>
        </div>
      </div>
    );
  }
  if (message.error) {
    return (
      <div className="msg msg--assistant">
        <div className="msg__error" role="alert">
          {message.error}
        </div>
      </div>
    );
  }
  return (
    <div className="msg msg--assistant">
      <div className="msg__body">
        <Prose text={message.text} citations={message.citations} onCitationClick={onCitationClick} />
        {message.citations && message.citations.length > 0 && <FeedbackBar />}
      </div>
    </div>
  );
}

interface ProseProps {
  text: string;
  citations?: Citation[];
  onCitationClick?: (index: number) => void;
}

function Prose({ text, citations, onCitationClick }: ProseProps) {
  const paragraphs = text.split(/\n{2,}/g);
  return (
    <div className="prose">
      {paragraphs.map((para, i) => (
        <p key={i}>{renderInline(para, citations, onCitationClick)}</p>
      ))}
    </div>
  );
}

function renderInline(
  text: string,
  citations: Citation[] | undefined,
  onCitationClick: ((i: number) => void) | undefined,
) {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/);
    if (m && citations) {
      const num = Number(m[1]);
      const cite = citations.find((c) => c.index === num);
      if (cite) {
        return (
          <button
            key={i}
            type="button"
            className="cite"
            onClick={() => onCitationClick?.(num)}
            aria-label={`Citation ${num} — ${cite.source.name}`}
          >
            {num}
          </button>
        );
      }
    }
    return <span key={i}>{p}</span>;
  });
}

function FeedbackBar() {
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const [copied, setCopied] = useState(false);
  return (
    <div className="msg__feedback" role="toolbar" aria-label="Message actions">
      <button
        type="button"
        className={`thumb${vote === "up" ? " thumb--on" : ""}`}
        onClick={() => setVote(vote === "up" ? null : "up")}
        aria-label="Helpful"
      >
        <Ico name="thumbUp" size={14} />
      </button>
      <button
        type="button"
        className={`thumb${vote === "down" ? " thumb--on" : ""}`}
        onClick={() => setVote(vote === "down" ? null : "down")}
        aria-label="Not helpful"
      >
        <Ico name="thumbDown" size={14} />
      </button>
      <button
        type="button"
        className="thumb"
        onClick={async () => {
          const target = document.querySelector(".msg--assistant .prose");
          try {
            await navigator.clipboard.writeText(target?.textContent || "");
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          } catch {
            /* ignore */
          }
        }}
        aria-label="Copy"
      >
        <Ico name="copy" size={14} />
      </button>
      <button type="button" className="thumb" aria-label="Regenerate (not yet implemented)" disabled>
        <Ico name="redo" size={14} />
      </button>
      {copied && <span className="msg__copied">Copied</span>}
    </div>
  );
}
