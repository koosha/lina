import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Ico } from "./Ico";
import "./Composer.css";

interface ComposerProps {
  variant?: "hero" | "compact";
  placeholder?: string;
  hint?: string;
  initialValue?: string;
  pending?: boolean;
  onSubmit: (text: string) => void;
  /** Auto-focus when mounted. */
  autoFocus?: boolean;
  /** Bind external state (e.g. when a chip is clicked on landing). */
  externalValue?: string;
}

export function Composer({
  variant = "hero",
  placeholder,
  hint,
  initialValue = "",
  pending = false,
  onSubmit,
  autoFocus,
  externalValue,
}: ComposerProps) {
  const [value, setValue] = useState(initialValue);
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (externalValue !== undefined) setValue(externalValue);
  }, [externalValue]);

  useEffect(() => {
    if (autoFocus) ref.current?.focus();
  }, [autoFocus]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    const max = variant === "hero" ? 200 : 140;
    el.style.height = `${Math.min(el.scrollHeight, max)}px`;
  }, [value, variant]);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || pending) return;
    onSubmit(trimmed);
    setValue("");
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  const showHint = variant === "hero" && !!hint;

  return (
    <div className={`composer composer--${variant}${pending ? " composer--pending" : ""}`}>
      <div className="composer__inner">
        <button type="button" className="composer__plus" aria-label="Attach (not implemented)">
          <Ico name="plus" size={16} />
        </button>
        <textarea
          ref={ref}
          className="composer__input"
          rows={1}
          value={value}
          placeholder={placeholder}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKey}
          disabled={pending}
          aria-label="Ask Lina"
        />
        <button
          type="button"
          className="composer__send"
          onClick={submit}
          disabled={!value.trim() || pending}
          aria-label="Send"
        >
          <Ico name="send" size={16} />
        </button>
      </div>
      {showHint && (
        <div className="composer__hint">
          <span className="mono">{hint}</span>
        </div>
      )}
    </div>
  );
}
