import { Ico } from "./Ico";
import { SOURCE_LIST } from "../lib/sources";
import type { Citation } from "../lib/types";
import "./CitationsDrawer.css";

interface CitationsDrawerProps {
  citations: Citation[];
  highlightedIndex: number | null;
}

export function CitationsDrawer({ citations, highlightedIndex }: CitationsDrawerProps) {
  return (
    <aside className="drawer" aria-label="Sources">
      <div className="drawer__head">
        <span className="eyebrow">Sources · {citations.length} used</span>
        <p className="drawer__lead">
          Every fact below is grounded in one of Lina's connected systems. Click a citation in the
          answer to focus it here.
        </p>
      </div>

      <ol className="drawer__list">
        {citations.map((c) => (
          <li
            key={c.index}
            className={`drawer__card${highlightedIndex === c.index ? " drawer__card--on" : ""}`}
            id={`citation-${c.index}`}
          >
            <div className="drawer__card-head">
              <span className="drawer__num">{c.index}</span>
              <span className="drawer__source">{c.source.name}</span>
            </div>
            <div className="drawer__label">{c.label}</div>
            {c.recordUrl && (
              <a
                className="drawer__link"
                href={c.recordUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                View record <Ico name="ext" size={12} />
              </a>
            )}
          </li>
        ))}
      </ol>

      <div className="drawer__foot">
        <span className="eyebrow">Connected systems</span>
        <ul className="drawer__systems">
          {SOURCE_LIST.map((s) => (
            <li key={s.id}>
              <span className="drawer__systems-name">{s.name}</span>
            </li>
          ))}
        </ul>
        <p className="drawer__systems-note">
          Lina respects your role-based access. Restricted records aren&apos;t shown.
        </p>
      </div>
    </aside>
  );
}
