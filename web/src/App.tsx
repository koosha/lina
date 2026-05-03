import { useCallback, useEffect, useRef, useState } from "react";
import { TopBar } from "./components/TopBar";
import { Landing } from "./pages/Landing";
import { Answered } from "./pages/Answered";
import { PassphraseGate } from "./pages/PassphraseGate";
import { ask, AskError, config as apiConfig } from "./lib/api";
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

  // `messages` is the visible state. `messagesRef` keeps a snapshot that
  // survives Back navigation so Forward can restore the chat. When the user
  // clears the chat via the New chat button we wipe the ref too so a stale
  // chat doesn't reappear.
  const [messages, setMessagesState] = useState<UiMessage[]>([]);
  const messagesRef = useRef<UiMessage[]>([]);
  const setMessages = useCallback(
    (m: UiMessage[] | ((prev: UiMessage[]) => UiMessage[])) => {
      setMessagesState((prev) => {
        const next = typeof m === "function" ? m(prev) : m;
        messagesRef.current = next;
        return next;
      });
    },
    [],
  );

  const [pendingChip, setPendingChip] = useState<string | undefined>(undefined);

  // Reset chip echo so the same chip can be re-clicked.
  useEffect(() => {
    if (pendingChip) {
      const t = setTimeout(() => setPendingChip(undefined), 50);
      return () => clearTimeout(t);
    }
  }, [pendingChip]);

  // Browser back/forward navigation between landing and answered states.
  // Forward into a chat entry restores from the ref; back to the initial
  // entry clears the visible messages but keeps the ref so a subsequent
  // Forward can restore them.
  useEffect(() => {
    function onPop(e: PopStateEvent) {
      const isChatState = !!(e.state && (e.state as { linaChat?: boolean }).linaChat);
      if (isChatState && messagesRef.current.length > 0) {
        setMessagesState(messagesRef.current);
      } else {
        setMessagesState([]);
      }
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
    // Wipe both the visible state and the snapshot so a Forward press after
    // Back doesn't resurrect the cleared conversation.
    messagesRef.current = [];
    setMessagesState([]);
    // Drop the chat entry from history so Back from landing leaves the app.
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
      <TopBar firstName={FIRST_NAME} userId={apiConfig.userId} />
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
  // Dedupe by source group (Matter & Spend / User Profiles / Outside Counsel).
  // At most three cards regardless of how many tool calls the supervisor
  // made. Aggregate row_count across all packets in the group; collect the
  // distinct result_types so the card label can show what was looked up.
  interface Bucket {
    firstIndex: number;
    source: ReturnType<typeof packetToSource>;
    resultTypes: Set<string>;
    rowCount: number;
    recordUrl?: string;
  }
  const buckets = new Map<string, Bucket>();
  packets.forEach((p, i) => {
    const source = packetToSource(p);
    const existing = buckets.get(source.id);
    const rows = p.row_count ?? 0;
    if (!existing) {
      buckets.set(source.id, {
        firstIndex: i,
        source,
        resultTypes: new Set(p.result_type ? [p.result_type] : []),
        rowCount: rows,
        recordUrl: p.record_url,
      });
      return;
    }
    if (p.result_type) existing.resultTypes.add(p.result_type);
    existing.rowCount += rows;
    if (!existing.recordUrl && p.record_url) existing.recordUrl = p.record_url;
  });
  return Array.from(buckets.values())
    .sort((a, b) => a.firstIndex - b.firstIndex)
    .map((b, i) => {
      const types = Array.from(b.resultTypes).map(humanizeResultType);
      const typeLabel = types.length === 0 ? "" : types.join(", ");
      const countLabel =
        b.rowCount > 0 ? `${b.rowCount} record${b.rowCount === 1 ? "" : "s"}` : "";
      const label = [typeLabel, countLabel].filter(Boolean).join(" · ");
      return {
        index: i + 1,
        source: b.source,
        label,
        recordUrl: b.recordUrl,
      };
    });
}
