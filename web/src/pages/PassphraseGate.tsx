import { useState, type FormEvent } from "react";
import "./PassphraseGate.css";

interface PassphraseGateProps {
  expected: string;
  onPass: () => void;
}

export function PassphraseGate({ expected, onPass }: PassphraseGateProps) {
  const [value, setValue] = useState("");
  const [err, setErr] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (value.trim() === expected) {
      try {
        sessionStorage.setItem("lina:gate", "ok");
      } catch {
        /* ignore */
      }
      onPass();
    } else {
      setErr("That passphrase doesn't match. Ask the Lina team for the current one.");
    }
  }

  return (
    <div className="gate">
      <form className="gate__card" onSubmit={submit} autoComplete="off">
        <span className="gate__badge">LINA</span>
        <h1 className="gate__title display">Sandbox preview</h1>
        <p className="gate__lead">
          Lina is in a private sandbox. Enter the passphrase shared with you to continue.
        </p>
        <label className="gate__label" htmlFor="gate-input">
          Passphrase
        </label>
        <input
          id="gate-input"
          type="password"
          className="gate__input"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setErr(null);
          }}
          autoFocus
        />
        {err && (
          <div className="gate__err" role="alert">
            {err}
          </div>
        )}
        <button type="submit" className="gate__submit">
          Continue
        </button>
        <p className="gate__foot">
          This is a non-production demo with sample data. Don&apos;t enter real client information.
        </p>
      </form>
    </div>
  );
}
