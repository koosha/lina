// Source-name mapping. Worker names never leak into the UI.
//
// Server-side worker IDs (`lina-redshift`, `lina-users`, `lina-vendors`) and
// the source_engine values returned in `ResultPacket` (`redshift`,
// `opensearch`) are translated to user-facing names here.
//
// Heuristic: result_type prefix disambiguates the two `opensearch` workers.

import type { FriendlySource, ResultPacket } from "./types";

export const FRIENDLY_SOURCES: Record<string, FriendlySource> = {
  matters: {
    id: "matters",
    name: "Matter & Spend",
    description:
      "Matters, budgets, invoices, billed hours, and timekeeper rates from the legal-spend warehouse.",
  },
  people: {
    id: "people",
    name: "User Profiles",
    description: "People, roles, departments, and reporting lines from the corporate directory.",
  },
  counsel: {
    id: "counsel",
    name: "Outside Counsel",
    description:
      "Outside lawyers and firms — practice areas, jurisdictions, and standard hourly rates.",
  },
};

export const SOURCE_LIST: FriendlySource[] = [
  FRIENDLY_SOURCES.matters,
  FRIENDLY_SOURCES.people,
  FRIENDLY_SOURCES.counsel,
];

const USER_RESULT_TYPES = new Set([
  "user_profile",
  "user_profiles",
  "manager_chain",
  "department_roster",
  "user_lookup",
]);

const VENDOR_RESULT_TYPES = new Set([
  "lawyer_profile",
  "lawyer_profiles",
  "lawyer_search",
  "practice_area_match",
  "timekeeper_lookup",
  "vendor_lookup",
]);

export function packetToSource(packet: ResultPacket): FriendlySource {
  // Prefer the explicit `source_id` set by the worker. Falls back to the
  // legacy heuristic on responses from older Lambda images that haven't
  // been redeployed with the Wave 3 packet shape yet.
  if (packet.source_id && FRIENDLY_SOURCES[packet.source_id]) {
    return FRIENDLY_SOURCES[packet.source_id];
  }
  if (packet.source_engine === "redshift") {
    return FRIENDLY_SOURCES.matters;
  }
  // OpenSearch — disambiguate users vs vendors by result_type.
  const resultType = (packet.result_type || "").toLowerCase();
  if (VENDOR_RESULT_TYPES.has(resultType) || resultType.includes("lawyer") || resultType.includes("vendor")) {
    return FRIENDLY_SOURCES.counsel;
  }
  if (USER_RESULT_TYPES.has(resultType) || resultType.includes("user") || resultType.includes("manager") || resultType.includes("department")) {
    return FRIENDLY_SOURCES.people;
  }
  // Reasonable default for unknown opensearch result_types.
  return FRIENDLY_SOURCES.people;
}

/** Humanize a snake_case result_type into a readable label. */
export function humanizeResultType(resultType: string): string {
  if (!resultType) return "Result";
  return resultType
    .split("_")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}
