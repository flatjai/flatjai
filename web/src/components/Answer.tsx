"use client";

import { ArrowRight } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

/** Reveals text word by word, about 30 words a second, the way an answer streams in.
 *  The parent keys this component by the text, so a new answer starts from zero. */
function useStreamed(text: string): string {
  const words = text.split(/(\s+)/);
  const [count, setCount] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setCount((n) => (n >= words.length ? n : n + 2)), 66);
    return () => clearInterval(id);
  }, [words.length]);
  return words.slice(0, count).join("");
}

/** Turn a computed relaxation into something the student can send back: "Raise my budget to HK$12,600". */
function asRefinement(relaxation: string): string {
  const money = relaxation.match(/HK\$[\d,]+/);
  if (relaxation.startsWith("Raising the budget") && money) return `Raise my budget to ${money[0]} a month`;
  if (relaxation.startsWith("No rooms")) return "A whole flat to share is fine";
  return relaxation;
}

type Props = { summary: string; relaxations: string[]; notes: string[]; onRefine: (text: string) => void };

export function Answer({ summary, relaxations, notes, onRefine }: Props) {
  const shown = useStreamed(summary);
  const complete = shown.length >= summary.length;
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[17px] leading-relaxed text-fg">
        {shown}
        {!complete ? <span className="fj-sunset ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 animate-pulse" /> : null}
      </p>
      {complete && relaxations.length ? (
        <div className="fj-rise flex flex-col gap-2">
          <p className="text-xs font-medium text-muted">Want more options?</p>
          <div className="flex flex-wrap gap-2">
            {relaxations.map((r) => (
              <button
                key={r}
                onClick={() => onRefine(asRefinement(r))}
                className="fj-sunset-soft group flex items-center gap-2 rounded-xl px-3.5 py-2 text-left text-sm text-coral-strong ring-1 ring-amber/15 transition hover:ring-amber/40"
              >
                {r}
                <ArrowRight size={14} weight="bold" className="flex-none transition-transform group-hover:translate-x-0.5" />
              </button>
            ))}
          </div>
        </div>
      ) : null}
      {complete
        ? notes.map((n) => (
            <p key={n} className="text-xs text-faint">
              {n}
            </p>
          ))
        : null}
    </div>
  );
}
