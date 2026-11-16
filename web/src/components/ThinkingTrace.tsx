"use client";

import {
  ArrowsClockwise,
  BookOpenText,
  Brain,
  CaretDown,
  Check,
  HouseLine,
  MagnifyingGlass,
  MapTrifold,
  Scales,
  type Icon,
} from "@phosphor-icons/react";
import { useEffect, useRef, useState } from "react";

import { STAGES, type Observation, type Stage } from "@/lib/api";
import { hkd } from "@/lib/format";
import { type RunState } from "@/lib/run-state";

import { ProfileChips } from "./ProfileChips";

type StageInfo = { icon: Icon; colour: string; doing: string };

const INFO: Record<Stage, StageInfo> = {
  understand: { icon: Brain, colour: "var(--coral)", doing: "Reading your brief" },
  plan: { icon: MapTrifold, colour: "var(--warn)", doing: "Planning where to look" },
  search: { icon: MagnifyingGlass, colour: "var(--sky)", doing: "Searching listing sites" },
  read: { icon: BookOpenText, colour: "var(--teal)", doing: "Reading listings and checking every figure" },
  match: { icon: Scales, colour: "var(--ok)", doing: "Checking homes against your limits" },
  reflect: { icon: ArrowsClockwise, colour: "var(--rose)", doing: "Deciding whether to look further" },
  answer: { icon: HouseLine, colour: "var(--coral)", doing: "Writing your shortlist" },
};

function doneTitle(stage: Stage, run: RunState): string {
  const c = run.counters;
  switch (stage) {
    case "understand":
      return "Understood your brief";
    case "plan":
      return run.round > 1 ? `Planned round ${run.round}: ${run.queries.length} searches` : `Planned ${run.queries.length} searches`;
    case "search":
      return c.prefiltered
        ? `Searched ${c.queries} times · ${c.candidates} homes found · ${c.prefiltered} ruled out by listed price or area`
        : `Searched ${c.queries} times · ${c.candidates} homes found`;
    case "read":
      return `Read ${c.pages} listings`;
    case "match":
      return c.cards ? `${c.cards} home${c.cards === 1 ? "" : "s"} fit your limits` : "No home fits all your limits yet";
    case "reflect":
      return run.note ? "Decided what to do next" : "Enough homes to answer";
    case "answer":
      return "Wrote your shortlist";
  }
}

const fmt = (s: number) => (s < 60 ? `${s.toFixed(s < 10 ? 1 : 0)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`);

/** Seconds since the run started, ticking between server events while the run is live. */
function useClock(serverNow: number, live: boolean): number {
  const anchor = useRef({ server: serverNow, wall: 0 });
  const [estimate, setEstimate] = useState(serverNow);
  useEffect(() => {
    anchor.current = { server: serverNow, wall: performance.now() };
  }, [serverNow]);
  useEffect(() => {
    if (!live) return;
    const id = setInterval(() => {
      const a = anchor.current;
      setEstimate(a.server + (performance.now() - a.wall) / 1000);
    }, 250);
    return () => clearInterval(id);
  }, [live]);
  return live ? Math.max(estimate, serverNow) : serverNow;
}

export function ThinkingTrace({ run }: { run: RunState }) {
  const live = run.status === "running" || run.status === "starting";
  const now = useClock(run.now, live);
  // open while working, folded away once the answer is in, unless the student toggles it
  // (the page keys this component by run, so each run starts fresh)
  const [toggled, setToggled] = useState<boolean | null>(null);
  const open = toggled ?? run.status !== "done";

  const seen = STAGES.filter((s) => run.timings[s]);
  const total = run.usage?.seconds ?? now;

  return (
    <div className="rounded-2xl bg-surface">
      <button
        onClick={() => setToggled(!open)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left text-sm"
        aria-expanded={open}
      >
        {live ? (
          <span className="fj-shimmer-text font-medium">Thinking · {fmt(now)}</span>
        ) : (
          <span className="font-medium text-muted">
            Thought for {fmt(total)}
            {run.counters.pages ? ` · read ${run.counters.pages} listings` : ""}
          </span>
        )}
        <CaretDown
          size={14}
          weight="bold"
          className={`ml-auto text-faint transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open ? (
        <ol className="relative flex flex-col gap-1 px-4 pb-4">
          {seen.map((stage, i) => {
            const timing = run.timings[stage]!;
            const active = timing.end === null && live;
            const info = INFO[stage];
            const last = i === seen.length - 1;
            const seconds = (timing.end ?? now) - timing.start;
            return (
              <li key={stage} className="fj-rise relative grid grid-cols-[28px_minmax(0,1fr)] gap-x-3">
                {!last ? <span className="absolute top-8 bottom-0 left-[13.5px] w-px bg-line" aria-hidden /> : null}
                <span
                  className="mt-0.5 grid size-7 place-items-center rounded-lg"
                  style={{ background: `color-mix(in srgb, ${info.colour} 16%, transparent)`, color: info.colour }}
                >
                  {active ? <info.icon size={15} weight="fill" className="fj-pulse-dot" /> : <info.icon size={15} weight="fill" />}
                </span>
                <div className="min-w-0 pb-3">
                  <div className="flex min-h-7 items-center gap-3">
                    <span className={`min-w-0 flex-1 truncate text-sm ${active ? "fj-shimmer-text font-medium" : "text-fg"}`}>
                      {active ? info.doing : doneTitle(stage, run)}
                    </span>
                    {!active && timing.end !== null ? <Check size={13} weight="bold" className="flex-none text-ok" /> : null}
                    <span className="w-12 flex-none text-right text-xs text-faint tabular-nums">{fmt(Math.max(seconds, 0))}</span>
                  </div>
                  <StageDetail stage={stage} run={run} active={active} />
                </div>
              </li>
            );
          })}
        </ol>
      ) : null}
    </div>
  );
}

function StageDetail({ stage, run, active }: { stage: Stage; run: RunState; active: boolean }) {
  if (stage === "understand" && run.profile) {
    return (
      <div className="mt-2">
        <ProfileChips profile={run.profile} missing={run.missing} />
      </div>
    );
  }
  if (stage === "plan" && run.queries.length) {
    return (
      <div className="mt-2 flex flex-col gap-2">
        <div className="flex flex-wrap gap-1.5">
          {run.queries.map((q) => (
            <span key={q} className="rounded-full bg-sky/10 px-2.5 py-1 text-xs text-sky">
              {q}
            </span>
          ))}
        </div>
        {run.rationale ? <p className="text-xs leading-relaxed text-muted">{run.rationale}</p> : null}
      </div>
    );
  }
  if (stage === "read") return <ReadingFeed pages={run.pages} inFlight={active ? run.inFlight : 0} />;
  if (stage === "reflect" && run.note) return <p className="mt-1 text-xs leading-relaxed text-muted">{run.note}</p>;
  return null;
}

const SHORT: Record<string, string> = {
  budget: "over budget",
  area: "too far",
  room: "not a room",
  bedrooms: "too few rooms",
  move_in: "free too late",
  duplicate: "duplicate",
  "over budget (listed rent)": "over budget",
  blocked: "site blocked",
  "gone or unreachable": "already let",
  "not a listing": "not a listing",
  "unsupported rent": "rent unclear",
  "extraction failed": "unreadable",
  "model error": "model error",
};

function shortReason(p: Observation): string {
  if (p.outcome === "fit") return "fits";
  return SHORT[p.failed ?? p.reason ?? ""] ?? p.reason ?? "skipped";
}

const OUTCOME = {
  fit: { colour: "var(--ok)" },
  rejected: { colour: "var(--bad)" },
  skipped: { colour: "var(--faint)" },
} as const;

/** Every listing the agent read, with what it decided, plus skeleton rows for reads in progress. */
function ReadingFeed({ pages, inFlight }: { pages: Observation[]; inFlight: number }) {
  const shown = pages.slice(-6);
  const hidden = pages.length - shown.length;
  return (
    <ul className="mt-2 flex flex-col gap-1">
      {hidden > 0 ? <li className="text-xs text-faint">+ {hidden} earlier</li> : null}
      {shown.map((p) => {
        const o = OUTCOME[p.outcome];
        return (
          <li key={p.url} className="fj-rise grid grid-cols-[8px_minmax(0,1fr)_auto] items-center gap-2.5 text-xs">
            <span className="size-2 rounded-full" style={{ background: o.colour }} />
            <span className="truncate text-fg">
              {p.title ?? decodeURIComponent(p.url.split("/").pop()?.split("?")[0] ?? p.url)}
              {p.rent_hkd ? <span className="text-faint"> · {hkd(p.rent_hkd)}</span> : null}
            </span>
            <span className="flex-none text-right" style={{ color: o.colour }} title={p.reason ?? undefined}>
              {shortReason(p)}
            </span>
          </li>
        );
      })}
      {Array.from({ length: Math.min(inFlight, 3) }, (_, i) => (
        <li key={`sk${i}`} className="grid grid-cols-[8px_minmax(0,1fr)_auto] items-center gap-2.5">
          <span className="fj-pulse-dot size-2 rounded-full bg-teal" />
          <span className="fj-skeleton h-3" style={{ width: `${[62, 48, 70][i]}%` }} />
          <span className="fj-skeleton h-3 w-12" />
        </li>
      ))}
    </ul>
  );
}
