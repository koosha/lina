import { useCallback, useEffect, useState } from "react";
import { TopBar } from "./components/TopBar";
import { Landing } from "./pages/Landing";
import { Answered } from "./pages/Answered";
import { PassphraseGate } from "./pages/PassphraseGate";
import { ask, AskError } from "./lib/api";
import { humanizeResultType, packetToSource } from "./lib/sources";
import type { Citation, ResultPacket, UiMessage } from "./lib/types";
import "./App.css";

const FIRST_NAME = (import.meta.env.VITE_LINA_FIRST_NAME as string | undefined) || "Jane";
const PASSPHRASE = (import.meta.env.VITE_LINA_PASSPHRASE as string | undefined) || "";

export function App() {
  const [gateOk, setGateOk] = useState(() => {
    if (!PASSPHRASE) return true;
    try {
      return sessionStorage.getItem("lina:gate") === "ok";
    } catch {
      return false;
    }
  });

  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [pendingChip, setPendingChip] = useState<string | undefined>(undefined);

  // Reset chip echo so the same chip can be re-clicked.
  useEffect(() => {
    if (pendingChip) {
      const t = setTimeout(() => setPendingChip(undefined), 50);
      return () => clearTimeout(t);
    }
  }, [pendingChip]);

  // Browser back from the answered state → return to landing. We push a
  // history entry on the first submission so a single back press undoes it.
  useEffect(() => {
    function onPop() {
      setMessages([]);
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const handleSubmit = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      const userId = `u-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const pendingId = `a-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

      setMessages((prev) => {
        if (prev.length === 0) {
          // Add one history entry for the chat session so Back returns to landing.
          window.history.pushState({ linaChat: true }, "");
        }
        return [
          ...prev,
          { id: userId, role: "user", text: trimmed },
          { id: pendingId, role: "assistant", text: "", pending: true },
        ];
      });

      try {
        const resp = await ask(trimmed);
        const citations = packetsToCitations(resp.worker_packets);
        const text =
          resp.answer_text && resp.answer_text.trim().length > 0
            ? resp.answer_text
            : "Lina returned no answer text. Please try rephrasing your question.";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId
              ? { ...m, pending: false, text, citations }
              : m,
          ),
        );
      } catch (err) {
        const errorText =
          err instanceof AskError
            ? err.message
            : "Something went wrong reaching Lina. Please try again in a moment.";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId ? { ...m, pending: false, error: errorText, text: "" } : m,
          ),
        );
      }
    },
    [],
  );

  function handleNewChat() {
    setMessages([]);
    // Drop the pushed history entry too so Back from landing leaves the app.
    if (window.history.state && (window.history.state as { linaChat?: boolean }).linaChat) {
      window.history.back();
    }
  }

  if (PASSPHRASE && !gateOk) {
    return <PassphraseGate expected={PASSPHRASE} onPass={() => setGateOk(true)} />;
  }

  const showAnswered = messages.length > 0;

  return (
    <div className="app">
      <TopBar firstName={FIRST_NAME} />
      {showAnswered ? (
        <Answered
          messages={messages}
          onSubmit={handleSubmit}
          onNewChat={handleNewChat}
        />
      ) : (
        <Landing
          firstName={FIRST_NAME}
          pendingValue={pendingChip}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  );
}

function packetsToCitations(packets: ResultPacket[]): Citation[] {
  // Dedupe by (source.id, result_type). The supervisor often retries the same
  // template (call → fail → retry with better params) and we don't want the
  // user to see five "Matter Lookup" cards for what they perceive as one
  // lookup. Keep the first occurrence's index, take the highest non-zero
  // row_count and the first non-empty record_url across duplicates.
  const merged = new Map<string, ResultPacket & { _firstIndex: number }>();
  packets.forEach((p, i) => {
    const key = `${packetToSource(p).id}::${p.result_type || ""}`;
    const existing = merged.get(key);
    if (!existing) {
      merged.set(key, { ...p, _firstIndex: i });
      return;
    }
    const existingRows = existing.row_count ?? 0;
    const newRows = p.row_count ?? 0;
    if (newRows > existingRows) existing.row_count = newRows;
    if (!existing.record_url && p.record_url) existing.record_url = p.record_url;
  });
  return Array.from(merged.values())
    .sort((a, b) => a._firstIndex - b._firstIndex)
    .map((p, i) => ({
      index: i + 1,
      source: packetToSource(p),
      label:
        humanizeResultType(p.result_type) +
        (p.row_count && p.row_count > 0
          ? ` · ${p.row_count} record${p.row_count === 1 ? "" : "s"}`
          : ""),
      recordUrl: p.record_url,
    }));
}
