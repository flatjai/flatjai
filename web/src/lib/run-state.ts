// Conversation and run state as a pure reducer over server events; components only render it.
import type { Card, ChatDetail, Counters, Observation, Profile, RunEvent, ShortlistItem, Stage, Usage } from "./api";

export type Turn = { role: "user" | "assistant"; text: string; runId?: string };

/** When each stage started and ended, in seconds since the run started (from the events' t). */
export type StageTiming = { start: number; end: number | null };

export type RunState = {
  status: "idle" | "starting" | "running" | "asking" | "done" | "error";
  runId: string | null;
  sessionId: string | null;
  brief: string | null; // the message this run answers
  turns: Turn[]; // the conversation before this run
  stage: Stage | null;
  timings: Partial<Record<Stage, StageTiming>>;
  now: number; // latest t seen
  profile: Profile | null;
  missing: string[];
  round: number;
  queries: string[];
  rationale: string | null;
  counters: Counters;
  inFlight: number;
  pages: Observation[];
  note: string | null;
  cards: Card[];
  question: { text: string; suggestions: string[] } | null;
  shortlist: ShortlistItem[];
  summary: string | null;
  relaxations: string[];
  notes: string[];
  usage: Usage | null;
  error: string | null;
};

export const initialRun: RunState = {
  status: "idle",
  runId: null,
  sessionId: null,
  brief: null,
  turns: [],
  stage: null,
  timings: {},
  now: 0,
  profile: null,
  missing: [],
  round: 0,
  queries: [],
  rationale: null,
  counters: { queries: 0, candidates: 0, pages: 0, cards: 0 },
  inFlight: 0,
  pages: [],
  note: null,
  cards: [],
  question: null,
  shortlist: [],
  summary: null,
  relaxations: [],
  notes: [],
  usage: null,
  error: null,
};

export type Action =
  | { kind: "start"; brief: string }
  | { kind: "started"; runId: string; sessionId: string }
  | { kind: "event"; event: RunEvent }
  | { kind: "fail"; message: string }
  | { kind: "load"; state: RunState }
  | { kind: "reset" };

export function runReducer(state: RunState, action: Action): RunState {
  switch (action.kind) {
    case "reset":
      return initialRun;
    case "load":
      return action.state;
    case "start": {
      // a new turn in the same conversation: the last run's exchange moves into the history
      const history = [...state.turns];
      if (state.brief) history.push({ role: "user", text: state.brief });
      const runId = state.runId ?? undefined;
      if (state.question) history.push({ role: "assistant", text: state.question.text, runId });
      else if (state.summary) history.push({ role: "assistant", text: state.summary, runId });
      else if (state.error) history.push({ role: "assistant", text: state.error, runId });
      return {
        ...initialRun,
        status: "starting",
        sessionId: state.sessionId,
        profile: state.profile,
        brief: action.brief,
        turns: history,
      };
    }
    case "started":
      return { ...state, runId: action.runId, sessionId: action.sessionId };
    case "fail":
      return { ...state, status: "error", error: action.message };
    case "event":
      return applyEvent(state, action.event);
  }
}

function applyEvent(prev: RunState, e: RunEvent): RunState {
  const stamped = (e.data as { t?: number }).t;
  const t = typeof stamped === "number" ? stamped : prev.now;
  const state = { ...prev, now: Math.max(prev.now, t) };
  switch (e.type) {
    case "state": {
      const timings = { ...state.timings };
      if (state.stage && state.stage !== e.data.stage) {
        timings[state.stage] = { start: timings[state.stage]?.start ?? t, end: t };
      }
      // a re-plan enters a stage again: it restarts its clock
      if (state.stage !== e.data.stage) timings[e.data.stage] = { start: t, end: null };
      return {
        ...state,
        status: "running",
        stage: e.data.stage,
        timings,
        profile: e.data.profile ?? state.profile,
        missing: e.data.missing ?? state.missing,
        round: e.data.round ?? state.round,
        queries: e.data.queries ?? state.queries,
        rationale: e.data.rationale ?? state.rationale,
      };
    }
    case "progress": {
      const { note, in_flight, t: _t, ...counters } = e.data;
      void _t;
      return {
        ...state,
        counters: { ...state.counters, ...counters },
        inFlight: in_flight ?? state.inFlight,
        note: note ?? state.note,
      };
    }
    case "observation":
      if (state.pages.some((p) => p.url === e.data.url)) return state;
      return { ...state, pages: [...state.pages, e.data] };
    case "card":
      // keyed by listing id: a resumed stream never shows a card twice
      if (state.cards.some((c) => c.listing_id === e.data.listing_id)) return state;
      return { ...state, cards: [...state.cards, e.data] };
    case "clarify":
      return {
        ...closeStage(state, t),
        status: "asking",
        question: { text: e.data.question, suggestions: e.data.suggestions },
      };
    case "done":
      return {
        ...closeStage(state, t),
        status: "done",
        inFlight: 0,
        summary: e.data.summary,
        shortlist: e.data.shortlist,
        relaxations: e.data.relaxations,
        notes: e.data.notes,
        counters: e.data.counters,
        usage: e.data.usage,
      };
    case "error":
      return { ...closeStage(state, t), status: "error", inFlight: 0, error: e.data.message };
  }
}

function closeStage(state: RunState, t: number): RunState {
  if (!state.stage) return state;
  const timing = state.timings[state.stage];
  return { ...state, timings: { ...state.timings, [state.stage]: { start: timing?.start ?? t, end: t } } };
}

/** Before the answer: cards in arrival order. After it: the ranked shortlist only (cards left out
 *  are duplicates that the Match stage found, or beyond the shortlist size). */
export function orderedCards(state: RunState): { card: Card; rank: number | null; reasons: string[] }[] {
  if (state.status !== "done" || !state.shortlist.length) {
    return state.cards.map((card) => ({ card, rank: null, reasons: [] }));
  }
  const byId = new Map(state.cards.map((c) => [c.listing_id, c]));
  return state.shortlist.flatMap((s) => {
    const card = byId.get(s.listing_id);
    return card ? [{ card, rank: s.rank, reasons: s.reasons }] : [];
  });
}

export const busy = (s: RunState) => s.status === "starting" || s.status === "running";

/** Run states that are final: nothing more will stream. */
export const SETTLED_RUNS = new Set(["done", "needs_input", "error"]);

/** Rebuild a chat from its stored events in one pass, through the same reducer the live stream
 *  uses, so a reopened chat reads exactly as it did live. A last turn that is still running comes
 *  back as `live`, with the seq to resume its stream after. */
export function buildChat(chat: ChatDetail): { state: RunState; live: { runId: string; after: number } | null } {
  let state = initialRun;
  chat.runs.forEach((turn) => {
    state = runReducer(state, { kind: "start", brief: turn.brief });
    state = runReducer(state, { kind: "started", runId: turn.id, sessionId: chat.session_id });
    for (const e of turn.events)
      state = runReducer(state, { kind: "event", event: { type: e.type, data: e.data } as RunEvent });
  });
  const last = chat.runs.at(-1);
  const live = last && !SETTLED_RUNS.has(last.status) ? { runId: last.id, after: last.events.at(-1)?.seq ?? 0 } : null;
  return { state, live };
}
