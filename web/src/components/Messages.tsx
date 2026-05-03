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

function LinaAvatar() {
  return (
    <span className="msg__avatar" aria-label="Lina">
      L
    </span>
  );
}

export function AssistantMsg({ message, onCitationClick }: AssistantMsgProps) {
  if (message.pending) {
    return (
      <div className="msg msg--assistant">
        <LinaAvatar />
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
        <LinaAvatar />
        <div className="msg__error" role="alert">
          {message.error}
        </div>
      </div>
    );
  }
  return (
    <div className="msg msg--assistant">
      <LinaAvatar />
      <div className="msg__body">
        <Prose text={message.text} citations={message.citations} onCitationClick={onCitationClick} />
        {message.citations && message.citations.length > 0 && (
          <FeedbackBar copyText={message.text} />
        )}
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
        if (b.kind === "table") {
          return (
            <div className="prose-table-wrap" key={i}>
              <table className="prose-table">
                {b.head.length > 0 && (
                  <thead>
                    <tr>
                      {b.head.map((cell, j) => (
                        <th key={j}>{renderInline(cell, citations, onCitationClick)}</th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {b.rows.map((row, ri) => (
                    <tr key={ri}>
                      {row.map((cell, ci) => (
                        <td key={ci}>{renderInline(cell, citations, onCitationClick)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
  | { kind: "h"; level: number; text: string }
  | { kind: "table"; head: string[]; rows: string[][] };

function parseBlocks(text: string): Block[] {
  // Pre-pass: when the supervisor glues prose to a numbered list (e.g.
  // "Fields: A | B | C1. Sam | active | Legal..."), split that boundary so
  // the numbered-pipe-rows detector can find the rows below.
  const split = text.replace(/([A-Za-z])\s*(\d+\.\s)/g, (full, pre, num, off, str) => {
    // Only insert a break when there's a `Fields:` or `:` declaration followed
    // by pipes on the line — avoids breaking up legitimate prose like
    // "...filed in 2024 1. Notice..."
    const before = str.slice(Math.max(0, off - 200), off + pre.length);
    if (/Fields:/i.test(before) && /\|/.test(before)) return `${pre}\n\n${num}`;
    return full;
  });
  const blocks: Block[] = [];
  for (const para of split.split(/\n{2,}/g)) {
    blocks.push(...parseParagraph(para));
  }
  return blocks;
}

function parseParagraph(para: string): Block[] {
  const lines = para.split("\n").map((l) => l.trimEnd());
  if (lines.length === 0) return [];

  // Heading.
  if (lines.length === 1) {
    const h = lines[0].match(/^(#{1,6})\s+(.+)$/);
    if (h) return [{ kind: "h", level: h[1].length, text: h[2] }];
  }

  // Bullet list.
  if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
    return [{ kind: "ul", items: lines.map((l) => l.replace(/^\s*[-*]\s+/, "")) }];
  }

  // Multi-line markdown table.
  const multi = parseMultilineTable(lines);
  if (multi) return [multi];

  // Single-line table where rows were joined with " | " separators (the
  // supervisor sometimes emits this when its response collapses newlines).
  const single = parseInlineTable(lines.join(" "));
  if (single) return [single];

  // Numbered pipe-rows: "1. a | b | c \n 2. d | e | f \n ...". Common when
  // the supervisor returns a list of records without using markdown table
  // syntax. Optionally pulls headers from a preceding "Fields: A | B | C"
  // declaration if it sits in the same paragraph.
  const numbered = parseNumberedPipeRows(para);
  if (numbered) return numbered;

  return [{ kind: "p", text: para }];
}

function parseNumberedPipeRows(text: string): Block[] | null {
  const segments: string[] = [];
  const re = /(?:^|\n)\s*\d+\.\s+([^\n]+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    segments.push(m[1].trim());
  }
  if (segments.length < 2) return null;
  if (!segments.every((s) => s.split("|").length >= 3)) return null;

  const rows = segments.map((s) => s.split("|").map((c) => c.trim()));
  const cols = mode(rows.map((r) => r.length));
  const filtered = rows.filter((r) => r.length === cols);
  if (filtered.length < 2) return null;

  let head: string[] = [];
  const fieldsMatch = text.match(/Fields:\s*([^\n]+?)(?=\s*\d+\.\s|\s*$)/i);
  if (fieldsMatch) {
    const cells = fieldsMatch[1]
      .split("|")
      .map((c) => c.trim().replace(/\s*\d+\.?$/, "").trim())
      .filter(Boolean);
    if (cells.length === cols) head = cells;
  }

  // Compose blocks: optional intro text (everything before "Fields:" or
  // before the first numbered row), then the table.
  const blocks: Block[] = [];
  const introCut = fieldsMatch
    ? text.indexOf(fieldsMatch[0])
    : text.search(/(?:^|\n)\s*\d+\.\s/);
  const intro = introCut > 0 ? text.slice(0, introCut).trim() : "";
  if (intro) blocks.push({ kind: "p", text: intro });
  blocks.push({ kind: "table", head, rows: filtered });
  return blocks;
}

function mode(nums: number[]): number {
  const counts = new Map<number, number>();
  for (const n of nums) counts.set(n, (counts.get(n) ?? 0) + 1);
  let best = nums[0];
  let bestCount = 0;
  for (const [n, c] of counts) {
    if (c > bestCount) {
      best = n;
      bestCount = c;
    }
  }
  return best;
}

function parseMultilineTable(lines: string[]): Block | null {
  // Need at least header, separator, and one row.
  if (lines.length < 3) return null;
  if (!isPipeRow(lines[0]) || !isPipeRow(lines[1]) || !isPipeRow(lines[2])) return null;
  if (!/^\s*\|?\s*:?-{3,}/.test(splitPipeRow(lines[1])[0] || "")) return null;
  // Confirm all separator cells are dashes.
  const sepCells = splitPipeRow(lines[1]);
  if (!sepCells.every((c) => /^:?-{3,}:?$/.test(c.trim()))) return null;
  const head = splitPipeRow(lines[0]);
  const rows: string[][] = [];
  for (let i = 2; i < lines.length; i++) {
    if (!isPipeRow(lines[i])) break;
    rows.push(splitPipeRow(lines[i]));
  }
  if (rows.length === 0) return null;
  return { kind: "table", head, rows };
}

function parseInlineTable(text: string): Block | null {
  // Detect a header followed by a separator like `|---|---|---|` where the
  // entire structure was joined into a single line.
  const sepIdx = text.search(/\|\s*-{3,}/);
  if (sepIdx < 0) return null;
  const head = splitPipeRow(text.slice(0, sepIdx));
  if (head.length < 2) return null;

  // Walk past the separator block.
  const afterSep = text.slice(sepIdx).replace(/^\|?(?:\s*:?-{3,}:?\s*\|)+/, "");
  // Split remaining text into rows by pipe-prefixed groups; the simplest
  // robust split treats every ` | ` not preceded by a header keyword as a
  // cell boundary, but that's brittle. Fall back to splitting on `|` and
  // chunking by `head.length`.
  const cells = splitPipeRow(afterSep);
  if (cells.length === 0) return null;
  const cols = head.length;
  const rows: string[][] = [];
  for (let i = 0; i < cells.length; i += cols) {
    const row = cells.slice(i, i + cols);
    if (row.length === cols && row.some((c) => c.trim() !== "")) {
      rows.push(row);
    }
  }
  if (rows.length === 0) return null;
  return { kind: "table", head, rows };
}

function isPipeRow(line: string): boolean {
  return /^\s*\|.*\|\s*$/.test(line) || (line.split("|").length >= 3 && /\|/.test(line));
}

function splitPipeRow(line: string): string[] {
  return line
    .replace(/^\s*\|/, "")
    .replace(/\|\s*$/, "")
    .split("|")
    .map((c) => c.trim());
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

interface FeedbackBarProps {
  copyText: string;
}

function FeedbackBar({ copyText }: FeedbackBarProps) {
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(copyText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* ignore */
    }
  }
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
      <button type="button" className="thumb" onClick={copy} aria-label="Copy">
        <Ico name="copy" size={14} />
      </button>
      <button type="button" className="thumb" aria-label="Regenerate (not yet implemented)" disabled>
        <Ico name="redo" size={14} />
      </button>
      {copied && <span className="msg__copied">Copied</span>}
    </div>
  );
}
