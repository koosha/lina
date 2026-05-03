import sampleQueriesJson from "../data/sample-queries.json";

interface SampleQueryRaw {
  id: string;
  category: string;
  text: string;
  backends: string[];
  expected_templates: string[];
  difficulty: "easy" | "medium" | "hard";
  notes?: string;
}

interface SampleQueriesFile {
  questions: SampleQueryRaw[];
}

const data = sampleQueriesJson as unknown as SampleQueriesFile;

export interface SampleQuery {
  id: string;
  text: string;
  difficulty: "easy" | "medium" | "hard";
  /** Friendly source ids derived from `backends`. */
  sourceIds: Array<"matters" | "people" | "counsel">;
}

const BACKEND_TO_SOURCE: Record<string, "matters" | "people" | "counsel"> = {
  redshift: "matters",
  opensearch_users: "people",
  opensearch_vendors: "counsel",
};

const ALL_QUERIES: SampleQuery[] = data.questions.map((q) => ({
  id: q.id,
  text: q.text,
  difficulty: q.difficulty,
  sourceIds: Array.from(
    new Set(
      q.backends
        .map((b) => BACKEND_TO_SOURCE[b])
        .filter((s): s is "matters" | "people" | "counsel" => Boolean(s)),
    ),
  ),
}));

export function getAllSampleQueries(): SampleQuery[] {
  return ALL_QUERIES;
}

/** Four chips for the landing page — mix of one-source and cross-source examples. */
export function getLandingChips(): SampleQuery[] {
  const easy = ALL_QUERIES.filter((q) => q.difficulty === "easy");
  const cross = ALL_QUERIES.filter((q) => q.sourceIds.length >= 2);
  const picks: SampleQuery[] = [];
  // Two single-source easy demos.
  if (easy[0]) picks.push(easy[0]);
  const otherEasy = easy.find((q) => q.id !== picks[0]?.id && !arraysEqual(q.sourceIds, picks[0]?.sourceIds || []));
  if (otherEasy) picks.push(otherEasy);
  // Two cross-source demos.
  if (cross[0]) picks.push(cross[0]);
  const otherCross = cross.find((q) => q.id !== cross[0]?.id);
  if (otherCross) picks.push(otherCross);
  return picks.slice(0, 4);
}

function arraysEqual(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((v, i) => v === b[i]);
}

/** Suggest a placeholder sample question for the composer. */
export function getComposerHint(): string {
  return "Try: How much has Walker billed on Acme v. Beta in 2024-Q4?";
}
