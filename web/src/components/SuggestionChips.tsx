import type { SampleQuery } from "../lib/sampleQueries";
import "./SuggestionChips.css";

interface SuggestionChipsProps {
  chips: SampleQuery[];
  onPick: (query: string) => void;
}

export function SuggestionChips({ chips, onPick }: SuggestionChipsProps) {
  return (
    <ul className="chips" aria-label="Suggested questions">
      {chips.map((c) => (
        <li key={c.id}>
          <button
            type="button"
            className="chips__chip"
            onClick={() => onPick(c.text)}
            title={c.text}
          >
            {truncate(c.text, 90)}
          </button>
        </li>
      ))}
    </ul>
  );
}

function truncate(s: string, n: number) {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}
