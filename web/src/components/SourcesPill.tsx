import { useState } from "react";
import { Ico } from "./Ico";
import { SOURCE_LIST } from "../lib/sources";
import "./SourcesPill.css";

export function SourcesPill() {
  const [open, setOpen] = useState(false);
  return (
    <div className="pill">
      <button
        type="button"
        className="pill__btn"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls="pill-popover"
      >
        <Ico name="lock" size={13} />
        <span>{SOURCE_LIST.length} connected systems</span>
        <Ico name="chev" size={13} />
      </button>
      {open && (
        <div className="pill__popover" id="pill-popover" role="dialog" aria-label="Connected systems">
          <p className="pill__lead">Lina answers from these systems on your behalf:</p>
          <ul className="pill__list">
            {SOURCE_LIST.map((s) => (
              <li key={s.id}>
                <span className="pill__list-name">{s.name}</span>
                <span className="pill__list-desc">{s.description}</span>
              </li>
            ))}
          </ul>
          <p className="pill__foot">Access is governed by your role permissions.</p>
        </div>
      )}
    </div>
  );
}
