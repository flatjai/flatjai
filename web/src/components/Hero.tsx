"use client";

import { BookOpenText, Brain, Calculator, Check, MapPin, SealCheck, Train } from "@phosphor-icons/react";
import { useState } from "react";

import { complete, hintsFrom, type Hints } from "@/lib/brief-hints";

import { Composer } from "./Composer";
import { Jai } from "./Jai";

/** The homepage has one focal point: the composer. Everything else supports it or steps back. */

const EXAMPLES = [
  { icon: Train, label: "Own room · 9k · HKUST", text: "Own room, max HK$9,000 a month, under 40 min to HKUST, from January, quiet" },
  { icon: MapPin, label: "2-bed share · 30k · Hang Hau", text: "2-bedroom flat to share with a friend, 30k total, near Hang Hau, move in February" },
  { icon: Calculator, label: "Studio · 15k · HKU", text: "Studio near HKU, up to 15k, 30 minutes to campus, from 1 March" },
];

const STEPS = [
  { icon: Brain, colour: "var(--coral)", text: "Understands your brief" },
  { icon: BookOpenText, colour: "var(--teal)", text: "Reads every listing" },
  { icon: SealCheck, colour: "var(--ok)", text: "Checks every figure" },
];

const PILLS: { key: keyof Hints; label: string; needed: boolean }[] = [
  { key: "budget", label: "Budget", needed: true },
  { key: "campus", label: "Campus", needed: true },
  { key: "moveIn", label: "Move-in", needed: true },
  { key: "commute", label: "Commute", needed: false },
];

/** What Jai picks up as you type: a pill lights up with its value; the hard limits Jai would
 *  otherwise ask about are outlined until given. */
function BriefPills({ hints, typing }: { hints: Hints; typing: boolean }) {
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="What Jai has picked up">
      {PILLS.map(({ key, label, needed }) => {
        const value = hints[key];
        return (
          <li
            key={key}
            className={`items-center gap-1 rounded-full px-2.5 py-1 text-xs transition-all duration-300 ${
              !needed && !value ? "hidden sm:flex" : "flex"
            } ${
              value
                ? "fj-sunset-soft text-coral-strong ring-1 ring-amber/25"
                : needed && typing
                  ? "text-muted ring-1 ring-line ring-dashed"
                  : "text-faint ring-1 ring-line-faint"
            }`}
          >
            {value ? <Check size={11} weight="bold" /> : null}
            {value ? value : label}
          </li>
        );
      })}
    </ul>
  );
}

export function Hero({ onSend }: { onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const hints = hintsFrom(text);
  const ready = complete(hints);
  const engaged = focused || text.length > 0;

  return (
    <section
      className="fj-home relative flex min-h-[calc(100dvh-var(--header-h)-48px)] flex-col items-center justify-center gap-9 overflow-x-clip py-2"
      data-engaged={engaged ? "" : undefined}
    >
      <div className="fj-field" aria-hidden />
      <div className="fj-horizon" aria-hidden />

      <div className="flex w-full flex-col items-center gap-5 text-center">
        <Jai mood={ready ? "excited" : "idle"} size={88} follow />
        <h1 className="text-[34px] leading-[1.08] font-bold tracking-[-0.02em] text-balance sm:text-[52px]">
          Find a home in Hong Kong, <span className="fj-sunset-text">without the guesswork.</span>
        </h1>
        <p className="max-w-md text-[15px] text-pretty text-muted sm:text-base">
          Tell Jai what you need. It reads the listings, checks every figure and shows the homes that truly fit.
        </p>
      </div>

      <div className="flex w-full max-w-2xl flex-col gap-3">
        <div className="fj-hero-composer shadow-[0_24px_80px_-28px_rgb(255_138_69/0.4)]">
          <Composer
            large
            autoFocus
            placeholder="A room near HKUST under 9k, 30 minutes to campus, from January…"
            onSend={onSend}
            onTextChange={setText}
            onFocusChange={setFocused}
            footer={<BriefPills hints={hints} typing={text.length > 0} />}
          />
        </div>
        <p className="fj-home-quiet h-4 text-center text-xs text-muted transition-opacity">
          {text.length === 0
            ? ""
            : ready
              ? "Jai has what it needs. Press Enter to search."
              : "Add a budget, campus and move-in date and Jai won't need to ask."}
        </p>
        <div className="fj-home-recede fj-chip-row -mx-4 px-4 sm:mx-0 sm:px-0">
          <span className="flex-none self-center pr-1 text-xs text-faint">Try</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.text}
              onClick={() => onSend(ex.text)}
              title={ex.text}
              className="flex flex-none items-center gap-2 rounded-full bg-surface px-3.5 py-2 text-[13px] text-muted ring-1 ring-line-faint transition hover:text-fg hover:ring-amber/40"
            >
              <ex.icon size={14} weight="fill" className="text-amber" />
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <ol className="fj-home-recede flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[13px] text-muted">
        {STEPS.map((s, i) => (
          <li key={s.text} className="flex items-center gap-2">
            <s.icon size={15} weight="fill" style={{ color: s.colour }} />
            {s.text}
            {i < STEPS.length - 1 ? <span className="ml-4 hidden h-px w-6 bg-line sm:block" aria-hidden /> : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
