import type { AskResponse } from "./types";

const API_BASE = (import.meta.env.VITE_LINA_API_BASE as string | undefined)?.replace(/\/$/, "");
const API_KEY = import.meta.env.VITE_LINA_API_KEY as string | undefined;
const USER_ID = (import.meta.env.VITE_LINA_USER_ID as string | undefined) || "user_jane_smith";

export class AskError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "AskError";
  }
}

export async function ask(query: string, signal?: AbortSignal): Promise<AskResponse> {
  if (!API_BASE || !API_KEY) {
    if (import.meta.env.DEV) {
      throw new AskError(
        "Lina is not configured. Build with VITE_LINA_API_BASE and VITE_LINA_API_KEY set, or copy `.env.example` to `.env.local`.",
        0,
      );
    }
    throw new AskError("Lina isn't reachable right now. Please try again shortly.", 0);
  }

  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({ user_id: USER_ID, query }),
    signal,
  });

  let payload: unknown;
  try {
    payload = await res.json();
  } catch {
    throw new AskError(`Server returned non-JSON response (status ${res.status}).`, res.status);
  }

  if (!res.ok) {
    const errorText =
      typeof payload === "object" && payload && "error" in payload
        ? String((payload as { error: unknown }).error)
        : `Request failed with status ${res.status}.`;
    if (res.status === 401 || res.status === 403) {
      throw new AskError("You don't have access to that information.", res.status);
    }
    throw new AskError(errorText, res.status);
  }

  return payload as AskResponse;
}

export const config = {
  apiBase: API_BASE,
  apiKey: API_KEY,
  userId: USER_ID,
};
