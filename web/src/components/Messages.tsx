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
  const blocks = parseBlocks(text);
  return (
    <div className="prose">
      {blocks.map((b, i) => {
        if (b.kind === "ul") {
          return (
            <ul key={i}>
              {b.items.map((item, j) => (
                <li key={j}>{renderInline(item, citations, onCitationClick)}</li>
              ))}
            </ul>
          );
        }
        if (b.kind === "h") {
          const Tag = (`h${Math.min(Math.max(b.level + 1, 2), 4)}` as "h2" | "h3" | "h4");
          return (
            <Tag key={i}>{renderInline(b.text, citations, onCitationClick)}</Tag>
          );
        }
        return <p key={i}>{renderInline(b.text, citations, onCitationClick)}</p>;
      })}
    </div>
  );
}

type Block =
  | { kind: "p"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "h"; level: number; text: string };

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  for (const para of text.split(/\n{2,}/g)) {
    const lines = para.split("\n");
    const heading = lines[0].match(/^(#{1,6})\s+(.+)$/);
    if (heading && lines.length === 1) {
      blocks.push({ kind: "h", level: heading[1].length, text: heading[2] });
      continue;
    }
    const isBulletList = lines.length > 0 && lines.every((l) => /^\s*[-*]\s+/.test(l));
    if (isBulletList) {
      blocks.push({
        kind: "ul",
        items: lines.map((l) => l.replace(/^\s*[-*]\s+/, "")),
      });
    } else {
      blocks.push({ kind: "p", text: para });
    }
  }
  return blocks;
}

function renderInline(
  text: string,
  citations: Citation[] | undefined,
  onCitationClick: ((i: number) => void) | undefined,
) {
  // Tokenize on citations, bold (**…**), and inline code (`…`).
  const parts = text.split(/(\[\d+\]|\*\*[^*\n]+?\*\*|`[^`\n]+?`)/g);
  return parts.map((p, i) => {
    const cite = p.match(/^\[(\d+)\]$/);
    if (cite && citations) {
      const num = Number(cite[1]);
      const found = citations.find((c) => c.index === num);
      if (found) {
        return (
          <button
            key={i}
            type="button"
            className="cite"
            onClick={() => onCitationClick?.(num)}
            aria-label={`Citation ${num} — ${found.source.name}`}
          >
            {num}
          </button>
        );
      }
    }
    const bold = p.match(/^\*\*([^*\n]+?)\*\*$/);
    if (bold) return <strong key={i}>{bold[1]}</strong>;
    const code = p.match(/^`([^`\n]+?)`$/);
    if (code) return <code key={i}>{code[1]}</code>;
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
