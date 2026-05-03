import "./TopBar.css";

interface TopBarProps {
  firstName?: string;
}

export function TopBar({ firstName = "Jane" }: TopBarProps) {
  const initial = (firstName.trim()[0] || "J").toUpperCase();
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
        <span
          className="topbar__avatar"
          role="img"
          aria-label={`Signed in as ${firstName}`}
        >
          {initial}
        </span>
      </div>
    </header>
  );
}
