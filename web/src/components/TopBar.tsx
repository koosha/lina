import { useEffect, useRef, useState } from "react";
import "./TopBar.css";

interface TopBarProps {
  firstName?: string;
  userId?: string;
}

export function TopBar({ firstName = "Jane", userId }: TopBarProps) {
  const initial = (firstName.trim()[0] || "J").toUpperCase();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!wrapRef.current) return;
      if (wrapRef.current.contains(e.target as Node)) return;
      setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <header className="topbar" role="banner">
      <div className="topbar__left">
        <span className="topbar__badge" aria-label="Lina">
          LINA
        </span>
        <span className="topbar__tagline">
          Legal Intelligence &amp; Navigation Assistant
        </span>
      </div>
      <div className="topbar__right">
        <div className="topbar__user" ref={wrapRef}>
          <button
            type="button"
            className="topbar__avatar topbar__avatar--btn"
            aria-haspopup="dialog"
            aria-expanded={open}
            aria-label={`Account: ${firstName}`}
            onClick={() => setOpen((v) => !v)}
          >
            {initial}
          </button>
          {open && (
            <div className="topbar__user-popover" role="dialog" aria-label="Account">
              <div className="topbar__user-name">{firstName}</div>
              {userId && <div className="topbar__user-id mono">{userId}</div>}
              <div className="topbar__user-note">Sandbox demo · sample data only</div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
