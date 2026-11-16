"use client";

import { ListMagnifyingGlass, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useReducer, useRef } from "react";

import { Answer } from "@/components/Answer";
import { Composer } from "@/components/Composer";
import { Hero } from "@/components/Hero";
import { Jai, type JaiMood } from "@/components/Jai";
import { ListingCard, ListingCardSkeleton } from "@/components/ListingCard";
import { ThinkingTrace } from "@/components/ThinkingTrace";
import { createRun, subscribeRun } from "@/lib/api";
import { busy as isBusy, initialRun, orderedCards, runReducer, type RunState } from "@/lib/run-state";

function moodOf(run: RunState): JaiMood {
  if (run.status === "error") return "sad";
  if (run.status === "asking") return "curious";
  if (run.status === "done") return run.shortlist.length ? "happy" : "sad";
  if (run.status === "starting") return "excited";
  if (run.stage === "read") return "reading";
  return run.status === "idle" ? "idle" : "thinking";
}

export default function Home() {
  const [run, dispatch] = useReducer(runReducer, initialRun);
  const unsubscribe = useRef<(() => void) | null>(null);
  const composerBar = useRef<HTMLDivElement>(null);
  const busy = isBusy(run);

  useEffect(() => () => unsubscribe.current?.(), []);

  // iOS: no pinch zoom on an app-like page (with maximum-scale=1 in the viewport)
  useEffect(() => {
    const stop = (e: Event) => e.preventDefault();
    document.addEventListener("gesturestart", stop);
    return () => document.removeEventListener("gesturestart", stop);
  }, []);

  // the thread's bottom padding follows the fixed composer's real height
  useLayoutEffect(() => {
    const el = composerBar.current;
    if (!el) return;
    const set = () => document.documentElement.style.setProperty("--composer-h", `${el.offsetHeight}px`);
    set();
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, [run.status === "idle"]); // eslint-disable-line react-hooks/exhaustive-deps

  // follow the run as it grows, unless the student has scrolled up to read
  const growth = run.pages.length + run.cards.length + (run.summary ? 1 : 0) + (run.question ? 1 : 0);
  useEffect(() => {
    if (run.status === "idle") return; // the homepage never scrolls itself
    const nearBottom = window.innerHeight + window.scrollY > document.body.scrollHeight - 400;
    if (nearBottom) window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }, [growth, run.stage, run.status]);

  const send = useCallback(
    async (text: string) => {
      unsubscribe.current?.();
      dispatch({ kind: "start", brief: text });
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
      try {
        const started = await createRun(text, crypto.randomUUID(), run.sessionId);
        dispatch({ kind: "started", runId: started.run_id, sessionId: started.session_id });
        unsubscribe.current = subscribeRun(
          started.run_id,
          (event) => dispatch({ kind: "event", event }),
          () => dispatch({ kind: "fail", message: "Lost the connection to FlatJai. Is the backend running?" }),
        );
      } catch (e) {
        dispatch({ kind: "fail", message: e instanceof Error ? e.message : "Could not reach FlatJai." });
      }
    },
    [run.sessionId],
  );

  const reset = () => {
    unsubscribe.current?.();
    dispatch({ kind: "reset" });
    window.scrollTo({ top: 0 });
  };

  const idle = run.status === "idle";
  const cards = orderedCards(run);
  // one card-shaped placeholder while listings are being read: a promise of work, not of results
  const skeletons = run.status === "running" && run.stage === "read" && run.inFlight > 0 ? 1 : 0;

  return (
    <>
      <div className="fj-glow" aria-hidden />
      <header className="fj-header">
        <div className="mx-auto flex h-full max-w-3xl items-center gap-2.5 px-4">
          <button onClick={reset} className="flex items-center gap-2" aria-label="FlatJai home">
            <Jai mood={idle ? "idle" : moodOf(run)} size={idle ? 26 : 30} follow={!idle} celebrate={run.cards.length} />
            <span className="text-[17px] font-bold tracking-tight">FlatJai</span>
            <span className="text-sm text-faint">揾樓仔</span>
          </button>
          <nav className="ml-auto flex items-center gap-1">
            <Link
              href="/runs"
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted hover:bg-raised hover:text-fg"
            >
              <ListMagnifyingGlass size={16} weight="bold" />
              <span className="hidden sm:inline">Runs</span>
            </Link>
            {!idle ? (
              <button
                onClick={reset}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted hover:bg-raised hover:text-fg"
              >
                <Plus size={16} weight="bold" />
                <span className="hidden sm:inline">New search</span>
              </button>
            ) : null}
          </nav>
        </div>
      </header>

      <main
        className="relative z-10 mx-auto w-full max-w-3xl px-4"
        style={{ paddingTop: "calc(var(--header-h) + 24px)", paddingBottom: idle ? 48 : "calc(var(--composer-h) + 32px)" }}
      >
        {idle ? (
          <Hero onSend={send} />
        ) : (
          <section className="flex flex-col gap-6">
            {run.turns.map((t, i) =>
              t.role === "user" ? (
                <UserBubble key={i} text={t.text} />
              ) : (
                <div key={i} className="flex gap-3 text-sm text-muted">
                  <Jai mood="idle" size={26} />
                  <p className="pt-1">{t.text}</p>
                </div>
              ),
            )}
            {run.brief ? <UserBubble text={run.brief} /> : null}

            <div className="flex gap-3">
              <Jai mood={moodOf(run)} size={34} className="mt-1" celebrate={run.cards.length} />
              <div className="flex min-w-0 flex-1 flex-col gap-4">
                {run.status === "starting" ? (
                  <div className="rounded-2xl bg-surface px-4 py-3 text-sm">
                    <span className="fj-shimmer-text font-medium">Jai is getting started…</span>
                  </div>
                ) : (
                  <ThinkingTrace key={run.runId ?? "pending"} run={run} />
                )}

                {run.question ? (
                  <div className="fj-rise flex flex-col gap-3">
                    <p className="text-[17px] leading-relaxed">{run.question.text}</p>
                    <div className="flex flex-wrap gap-2">
                      {run.question.suggestions.map((s) => (
                        <button
                          key={s}
                          onClick={() => send(s)}
                          className="fj-sunset-soft rounded-xl px-3.5 py-2 text-sm text-coral-strong ring-1 ring-amber/15 transition hover:ring-amber/40"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}

                {run.summary ? (
                  <Answer
                    key={run.summary}
                    summary={run.summary}
                    relaxations={run.relaxations}
                    notes={run.notes}
                    onRefine={send}
                  />
                ) : null}

                {run.error ? (
                  <div className="fj-rise rounded-xl bg-bad/10 px-4 py-3 text-sm text-bad">{run.error}</div>
                ) : null}
              </div>
            </div>

            {cards.length || skeletons ? (
              <div className="flex flex-col gap-3 sm:pl-[46px]">
                <p className="text-xs font-medium tracking-wide text-faint uppercase">
                  {run.status === "done" ? "Your shortlist" : cards.length ? "Homes that fit so far" : "Checking listings…"}
                </p>
                {cards.map(({ card, rank, reasons }) => (
                  <ListingCard key={card.listing_id} card={card} rank={rank} reasons={reasons} campus={run.profile?.campus} />
                ))}
                {Array.from({ length: skeletons }, (_, i) => (
                  <ListingCardSkeleton key={`sk${i}`} />
                ))}
              </div>
            ) : null}

            {run.usage && run.runId ? (
              <p className="text-xs text-faint tabular-nums sm:pl-[46px]">
                {run.usage.model_calls} model calls · {run.usage.fetches} pages fetched ·{" "}
                <Link href={`/runs/${run.runId}`} className="text-coral-strong hover:text-coral">
                  inspect this run
                </Link>
              </p>
            ) : null}
          </section>
        )}
      </main>

      {!idle ? (
        <div ref={composerBar} className="fj-composer-bar">
          <div className="mx-auto max-w-3xl">
            <Composer
              disabled={busy}
              placeholder={
                busy
                  ? "Jai is working on it…"
                  : run.status === "asking"
                    ? "Answer Jai…"
                    : "Refine: cheaper, only Tseung Kwan O, must be furnished…"
              }
              onSend={send}
            />
          </div>
        </div>
      ) : null}
    </>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="fj-rise flex justify-end">
      <p className="max-w-[85%] rounded-2xl rounded-br-md bg-raised-2 px-4 py-2.5 text-[15px] text-pretty text-fg">{text}</p>
    </div>
  );
}
