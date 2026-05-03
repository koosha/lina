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
  const [initialQuestion, setInitialQuestion] = useState<string>("");
  const [pendingChip, setPendingChip] = useState<string | undefined>(undefined);

  // Reset chip echo so the same chip can be re-clicked.
  useEffect(() => {
    if (pendingChip) {
      const t = setTimeout(() => setPendingChip(undefined), 50);
      return () => clearTimeout(t);
    }
  }, [pendingChip]);

  const handleSubmit = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;

      const userId = `u-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const pendingId = `a-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

      setMessages((prev) => {
        const isFirst = prev.length === 0;
        if (isFirst) setInitialQuestion(trimmed);
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
    setInitialQuestion("");
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
          initialQuestion={initialQuestion}
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
  return packets.map((p, i) => ({
    index: i + 1,
    source: packetToSource(p),
    label: humanizeResultType(p.result_type) +
      (p.row_count !== undefined ? ` · ${p.row_count} record${p.row_count === 1 ? "" : "s"}` : ""),
    recordUrl: p.record_url,
  }));
}
