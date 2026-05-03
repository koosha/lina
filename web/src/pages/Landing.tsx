import { useMemo } from "react";
import { Composer } from "../components/Composer";
import { SuggestionChips } from "../components/SuggestionChips";
import { SourcesPill } from "../components/SourcesPill";
import { Disclaimer } from "../components/Disclaimer";
import { getComposerHint, getLandingChips } from "../lib/sampleQueries";
import "./Landing.css";

interface LandingProps {
  firstName: string;
  pendingValue?: string;
  onSubmit: (text: string) => void;
}

export function Landing({ firstName, pendingValue, onSubmit }: LandingProps) {
  const chips = useMemo(() => getLandingChips(), []);
  const hint = getComposerHint();
  return (
    <div className="landing">
      <div className="landing__center">
        <span className="eyebrow">Welcome back, {firstName}</span>
        <h1 className="display landing__display">What can I help you with?</h1>

        <div className="landing__composer">
          <Composer
            variant="hero"
            placeholder="Ask Lina anything about matters, people, or outside counsel…"
            hint={hint}
            externalValue={pendingValue}
            onSubmit={onSubmit}
            autoFocus
          />
        </div>

        <SuggestionChips chips={chips} onPick={onSubmit} />

        <div className="landing__pill">
          <SourcesPill />
        </div>
      </div>

      <div className="landing__disclaimer">
        <Disclaimer />
      </div>
    </div>
  );
}
