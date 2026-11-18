"use client";

import { ChatsCircle, ListMagnifyingGlass, Plus } from "@phosphor-icons/react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useLayoutEffect, useReducer, useRef, useState } from "react";

import { Answer } from "@/components/Answer";
import { ChatDrawer, ChatMenu, ChatRail } from "@/components/ChatList";
import { Composer } from "@/components/Composer";
import { Hero } from "@/components/Hero";
import { Jai, type JaiMood } from "@/components/Jai";
import { ListingCard, ListingCardSkeleton } from "@/components/ListingCard";
import { ThinkingTrace } from "@/components/ThinkingTrace";
import { createRun, subscribeRun, type ChatDetail, type RunEvent } from "@/lib/api";
import { forgetChat, goToChat, loadChat, peekChat, refreshChats } from "@/lib/chats";
import { buildChat, busy as isBusy, initialRun, orderedCards, runReducer, type RunState } from "@/lib/run-state";

function moodOf(run: RunState): JaiMood {
  if (run.status === "error") return "sad";
  if (run.status === "asking") return "curious";
  if (run.status === "done") return run.shortlist.length ? "happy" : "sad";
  if (run.status === "starting") return "excited";
  if (run.stage === "read") return "reading";
  return run.status === "idle" ? "idle" : "thinking";
}

const TERMINAL = new Set(["done", "clarify", "error"]);
const LOST = "Lost the connection to FlatJai. Is the backend running?";

// the chat id lives in the URL (?c=), read with useSearchParams: Suspense lets the shell prerender
export default function Home() {
  return (
    <Suspense>
      <ChatPage />
    </Suspense>
  );
}

function ChatPage() {
  const [run, dispatch] = useReducer(runReducer, initialRun);
  const unsubscribe = useRef<(() => void) | null>(null);
  const composerBar = useRef<HTMLDivElement>(null);
  const busy = isBusy(run);
  const chatId = useSearchParams().get("c");
  const [loadingChat, setLoadingChat] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const closeDrawer = useCallback(() => setDrawer(false), []);
  const loadSeq = useRef(0); // a newer open, reply or reset makes an older load drop its result
  const [restored, setRestored] = useState(false); // a reopened chat appears at once, without entrance animations
  const sessionRef = useRef<string | null>(null);
  useLayoutEffect(() => {
    sessionRef.current = run.sessionId;
  }, [run.sessionId]);

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

  // stream a run; when it settles, the chat list and this chat's cached copy are out of date
  const follow = useCallback((runId: string, sessionId: string, after = 0) => {
    unsubscribe.current?.();
    unsubscribe.current = subscribeRun(
      runId,
      (event: RunEvent) => {
        dispatch({ kind: "event", event });
        if (TERMINAL.has(event.type)) {
          forgetChat(sessionId);
          void refreshChats();
        }
      },
      () => dispatch({ kind: "fail", message: LOST }),
      after,
    );
  }, []);

  // show a chat rebuilt from its stored events in one pass (one render); a turn still running
  // resumes streaming after the last event shown
  const showChat = useCallback(
    (chat: ChatDetail) => {
      const { state, live } = buildChat(chat);
      sessionRef.current = chat.session_id;
      dispatch({ kind: "load", state });
      setRestored(!live);
      setLoadingChat(false);
      if (live) follow(live.runId, chat.session_id, live.after);
      // open at the latest turn, the way it was left
      requestAnimationFrame(() => document.getElementById("fj-last-brief")?.scrollIntoView({ block: "start" }));
    },
    [follow],
  );

  // open a previous chat: from the cache in the same frame, else one request
  const openChat = useCallback(
    async (sessionId: string) => {
      const seq = ++loadSeq.current;
      unsubscribe.current?.();
      unsubscribe.current = null;
      const cached = peekChat(sessionId);
      if (cached) return showChat(cached);
      dispatch({ kind: "reset" });
      setLoadingChat(true);
      try {
        const chat = await loadChat(sessionId);
        if (seq === loadSeq.current) showChat(chat);
      } catch (e) {
        if (seq !== loadSeq.current) return;
        setLoadingChat(false);
        const gone = e instanceof Error && e.message.includes("404");
        dispatch({ kind: "fail", message: gone ? "This chat is no longer available." : LOST });
      }
    },
    [showChat],
  );

  // the URL decides which chat is open: a new ?c= opens it, none means a fresh homepage
  useEffect(() => {
    if (chatId && chatId !== sessionRef.current) {
      void openChat(chatId);
    } else if (!chatId && sessionRef.current) {
      loadSeq.current++;
      unsubscribe.current?.();
      unsubscribe.current = null;
      setLoadingChat(false);
      dispatch({ kind: "reset" });
      window.scrollTo({ top: 0 });
    }
  }, [chatId, openChat]);

  // follow the run as it grows, unless the student has scrolled up to read
  const growth = run.pages.length + run.cards.length + (run.summary ? 1 : 0) + (run.question ? 1 : 0);
  useEffect(() => {
    if (run.status === "idle" || loadingChat) return; // the homepage never scrolls itself
    const nearBottom = window.innerHeight + window.scrollY > document.body.scrollHeight - 400;
    if (nearBottom) window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
  }, [growth, run.stage, run.status, loadingChat]);

  const send = useCallback(
    async (text: string) => {
      loadSeq.current++; // a reply ends any load still in flight
      setLoadingChat(false);
      setRestored(false);
      unsubscribe.current?.();
      dispatch({ kind: "start", brief: text });
      window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
      try {
        const started = await createRun(text, crypto.randomUUID(), run.sessionId);
        dispatch({ kind: "started", runId: started.run_id, sessionId: started.session_id });
        // a new chat gets its URL now; the list shows it and any cached copy is stale
        sessionRef.current = started.session_id;
        if (new URLSearchParams(window.location.search).get("c") !== started.session_id)
          goToChat(started.session_id, { replace: true });
        forgetChat(started.session_id);
        void refreshChats();
        follow(started.run_id, started.session_id);
      } catch (e) {
        dispatch({
          kind: "fail",
          message: e instanceof Error ? e.message : "Could not reach FlatJai.",
        });
      }
    },
    [run.sessionId, follow],
  );

  const reset = () => {
    loadSeq.current++;
    unsubscribe.current?.();
    unsubscribe.current = null;
    setLoadingChat(false);
    dispatch({ kind: "reset" });
    window.scrollTo({ top: 0 });
    if (chatId) goToChat(null);
  };

  const idle = run.status === "idle" && !loadingChat;
  const cards = orderedCards(run);
  // one card-shaped placeholder while listings are being read: a promise of work, not of results
  const skeletons = run.status === "running" && run.stage === "read" && run.inFlight > 0 ? 1 : 0;

  return (
    <>
      <div className="fj-glow" aria-hidden />
      {!idle ? <ChatRail activeId={run.sessionId ?? chatId} /> : null}
      <ChatDrawer open={drawer} onClose={closeDrawer} activeId={run.sessionId ?? chatId} />
      <header className="fj-header fj-beside-rail">
        <div className="mx-auto flex h-full max-w-3xl items-center gap-2.5 px-4">
          {!idle ? (
            <button
              onClick={() => setDrawer(true)}
              className="-ml-1.5 rounded-lg p-1.5 text-faint transition-colors hover:text-fg lg:hidden"
              aria-label="Previous chats"
            >
              <ChatsCircle size={20} />
            </button>
          ) : null}
          <button onClick={reset} className="flex items-center gap-2" aria-label="FlatJai home">
            <Jai mood={idle ? "idle" : moodOf(run)} size={idle ? 26 : 30} follow={!idle} celebrate={run.cards.length} />
            <span className="text-[17px] font-bold tracking-tight">FlatJai</span>
            <span className="text-sm text-faint">揾樓仔</span>
          </button>
          <nav className="ml-auto flex items-center gap-1">
            {idle ? <ChatMenu /> : null}
            {!idle && run.runId ? (
              <Link
                href={`/runs/${run.runId}`}
                title="See every stage, model call and tool call of this turn"
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted hover:bg-raised hover:text-fg"
              >
                <ListMagnifyingGlass size={16} weight="bold" />
                <span className="hidden sm:inline">Inspect</span>
              </Link>
            ) : null}
            {!idle ? (
              <button
                onClick={reset}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm text-muted hover:bg-raised hover:text-fg"
              >
                <Plus size={16} weight="bold" />
                <span className="hidden sm:inline">New chat</span>
              </button>
            ) : null}
          </nav>
        </div>
      </header>

      <div className="fj-beside-rail">
        <main
          className={`relative z-10 mx-auto w-full max-w-3xl px-4 ${restored ? "fj-restored" : ""}`}
          style={{
            paddingTop: "calc(var(--header-h) + 24px)",
            paddingBottom: idle ? 48 : "calc(var(--composer-h) + 32px)",
          }}
        >
          {idle ? (
            <Hero onSend={send} />
          ) : loadingChat ? (
            <div className="flex items-center gap-3 pt-2 text-sm">
              <Jai mood="reading" size={30} />
              <span className="fj-shimmer-text font-medium">Opening this chat…</span>
            </div>
          ) : (
            <section className="flex flex-col gap-6">
              {run.turns.map((t, i) =>
                t.role === "user" ? (
                  <UserBubble key={i} text={t.text} />
                ) : (
                  <div key={i} className="group flex gap-3 text-sm text-muted">
                    <Jai mood="idle" size={26} />
                    <div className="min-w-0 pt-1">
                      <p>{t.text}</p>
                      {t.runId ? (
                        <Link
                          href={`/runs/${t.runId}`}
                          className="mt-1 inline-block text-xs text-faint/0 transition-colors group-hover:text-faint hover:!text-coral-strong focus:text-faint"
                        >
                          inspect this turn
                        </Link>
                      ) : null}
                    </div>
                  </div>
                ),
              )}
              {run.brief ? <UserBubble text={run.brief} id="fj-last-brief" /> : null}

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
                    {run.status === "done"
                      ? "Your shortlist"
                      : cards.length
                        ? "Homes that fit so far"
                        : "Checking listings…"}
                  </p>
                  {cards.map(({ card, rank, reasons }) => (
                    <ListingCard
                      key={card.listing_id}
                      card={card}
                      rank={rank}
                      reasons={reasons}
                      campus={run.profile?.campus}
                    />
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
      </div>

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

function UserBubble({ text, id }: { text: string; id?: string }) {
  return (
    <div id={id} className="fj-rise flex scroll-mt-[calc(var(--header-h)+24px)] justify-end">
      <p className="max-w-[85%] rounded-2xl rounded-br-md bg-raised-2 px-4 py-2.5 text-[15px] text-pretty text-fg">
        {text}
      </p>
    </div>
  );
}
