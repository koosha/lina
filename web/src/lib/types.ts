// Wire shapes match `lina_supervisor.lambda_handler.handler` response.

export type SourceEngine = "redshift" | "opensearch";

export interface ResultPacket {
  source_engine: SourceEngine;
  /**
   * Stable user-facing source group ("matters" | "people" | "counsel").
   * Added by the workers in Wave 3 — preferred over the result_type
   * heuristic. May be missing on older deployments; fall back to
   * source_engine + result_type when absent.
   */
  source_id?: FriendlySourceId;
  result_type: string;
  metrics?: Array<Record<string, unknown>>;
  rows?: Array<Record<string, unknown>>;
  row_count?: number;
  truncated?: boolean;
  sql_trace_id?: string;
  // Optional record URL for "View record" link if the worker returned one.
  record_url?: string;
}

export interface AskResponse {
  answer_text: string;
  worker_call_count: number;
  worker_packets: ResultPacket[];
  truncated: boolean;
}

export interface ApiError {
  error: string;
}

export type FriendlySourceId = "matters" | "people" | "counsel";

export interface FriendlySource {
  id: FriendlySourceId;
  name: string;
  /** What's in this source, in plain language. Shown in the drawer footer. */
  description: string;
}

export interface Citation {
  /** 1-based citation number in the answer. */
  index: number;
  source: FriendlySource;
  /** Short label (e.g. result_type humanized). */
  label: string;
  /** Optional URL to the source record. */
  recordUrl?: string;
}

export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  pending?: boolean;
  error?: string;
}
