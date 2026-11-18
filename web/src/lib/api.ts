// Client for the FlatJai request API. Types mirror backend/src/flatjai/{schemas,agent/state,tools/cost}.py.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Profile = {
  budget_hkd_month: number | null;
  budget_is_total: boolean;
  campus: string | null;
  max_commute_min: number | null;
  districts: string[];
  room_only: boolean | null;
  bedrooms: number | null;
  flatmates: number | null;
  move_in: string | null;
  lease_months: number | null;
  soft_preferences: string[];
};

export type Listing = {
  source_url: string;
  portal: string;
  title: string;
  rent_hkd_month: number;
  saleable_sqft: number | null;
  gross_sqft: number | null;
  bedrooms: number | null;
  room_only: boolean;
  bathroom?: "private" | "shared" | null;
  lease_months?: number | null;
  furnished: boolean | null;
  estate: string | null;
  address: string | null;
  district: string | null;
  mgmt_fee_included: boolean | null;
  mgmt_fee_hkd_month: number | null;
  agent_fee: "half" | "full" | "none" | "unknown";
  available_from: string | null;
  evidence: Record<string, string>;
};

export type CostItem = { label: string; hkd: number; assumed: boolean };
export type Cost = { monthly_hkd: number; move_in_hkd: number; monthly_items: CostItem[]; move_in_items: CostItem[] };
export type Check = { name: string; ok: boolean | null; detail: string; value: number | null };

export type CommuteLeg = {
  mode: "walk" | "bus" | "minibus" | "mtr" | "tram" | "ferry";
  text: string;
  minutes: number;
  path?: [number, number][]; // the leg's real line, from OpenTripPlanner
  color?: string | null; // the line's own colour (MTR)
};
export type RoutePlace = {
  name: string;
  kind: "home" | "station" | "board" | "alight" | "campus";
  lat: number;
  lon: number;
};
export type Commute = {
  minutes: number;
  legs: CommuteLeg[];
  method: string;
  precision: "building" | "area";
  route?: RoutePlace[];
};

export type Card = {
  listing_id: number;
  ask?: { questions: string[]; message: string };
  commute?: Commute | null;
  listing: Listing;
  cost: Cost;
  checks: Check[];
  fetched_at: string;
  unverified_fields: string[];
};

export type Counters = {
  queries: number;
  candidates: number;
  pages: number;
  cards: number;
  prefiltered?: number; // skipped from their list-page card alone (listed rent over budget, or too far)
};
export type ShortlistItem = { listing_id: number; rank: number; reasons: string[] };
export type Usage = {
  seconds: number;
  model_calls: number;
  tokens_in: number;
  tokens_out: number;
  fetches: number;
  rounds: number;
};

export const STAGES = ["understand", "plan", "search", "read", "match", "reflect", "answer"] as const;
export type Stage = (typeof STAGES)[number];

export type Observation = {
  url: string;
  title: string | null;
  district?: string | null;
  rent_hkd?: number | null;
  outcome: "fit" | "rejected" | "skipped";
  failed?: string | null; // which hard check failed: budget, area, room, bedrooms, move_in
  reason: string | null;
};

// every event carries t: seconds since the run started
export type RunEvent =
  | {
      type: "state";
      data: {
        t?: number;
        stage: Stage;
        profile?: Profile;
        missing?: string[];
        round?: number;
        queries?: string[];
        rationale?: string;
      };
    }
  | { type: "progress"; data: Counters & { note?: string; in_flight?: number; t?: number } }
  | { type: "observation"; data: Observation & { t?: number } }
  | { type: "card"; data: Card }
  | { type: "clarify"; data: { question: string; suggestions: string[]; missing: string[] } }
  | {
      type: "done";
      data: {
        summary: string;
        shortlist: ShortlistItem[];
        relaxations: string[];
        notes: string[];
        counters: Counters;
        usage: Usage;
      };
    }
  | { type: "error"; data: { message: string; retry: boolean } };

const EVENT_TYPES = ["state", "progress", "observation", "clarify", "card", "token", "done", "error"] as const;
const TERMINAL = new Set(["done", "error", "clarify"]);

export type RunStarted = { run_id: string; session_id: string };

export async function createRun(brief: string, clientKey: string, sessionId?: string | null): Promise<RunStarted> {
  const res = await fetch(`${API_URL}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brief, client_key: clientKey, session_id: sessionId ?? null }),
  });
  if (!res.ok) throw new Error(`Could not start the search (HTTP ${res.status}).`);
  return res.json();
}

/** Subscribe to a run's events. EventSource reconnects by itself and sends Last-Event-ID, so the
 *  server resumes without loss; we close it at the run's terminal event. Returns an unsubscribe. */
export function subscribeRun(
  runId: string,
  onEvent: (e: RunEvent) => void,
  onConnectionError: () => void,
  after = 0, // the last event seq already shown: a reopened chat streams only what is new
) {
  const source = new EventSource(`${API_URL}/runs/${runId}/events${after ? `?after=${after}` : ""}`);
  for (const type of EVENT_TYPES) {
    source.addEventListener(type, (msg) => {
      onEvent({ type, data: JSON.parse((msg as MessageEvent).data) } as RunEvent);
      if (TERMINAL.has(type)) source.close();
    });
  }
  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) onConnectionError();
  };
  return () => source.close();
}

// Run inspector -------------------------------------------------------------------------------

export type RunInfo = {
  id: string;
  session_id: string;
  brief: string;
  status: string;
  stage: string;
  model_profile: string;
  model: string;
  started_at: string;
  ended_at: string | null;
};

export type Span = {
  id: string;
  parent_id: string | null;
  name: string;
  kind: "stage" | "model" | "tool";
  started_at: string;
  ms: number;
  tokens_in: number;
  tokens_out: number;
  error: string | null;
  attrs: Record<string, unknown>;
};

export type Trace = {
  run: RunInfo;
  totals: Record<string, { count: number; tokens_in: number; tokens_out: number }>;
  spans: Span[];
};

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return res.json();
}

export const listRuns = () => getJson<RunInfo[]>("/runs");

export type Turn = {
  id: string;
  brief: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  model: string;
  homes: number;
};
export type Conversation = { session_id: string; started_at: string; last_at: string; runs: Turn[] };

/** A stored event, exactly as the run's stream sent it. */
export type StoredEvent = { seq: number; type: RunEvent["type"]; data: RunEvent["data"] };
/** One chat with every turn's events: enough to rebuild the page in one request. */
export type ChatDetail = Omit<Conversation, "runs"> & { runs: (Turn & { events: StoredEvent[] })[] };
export const getChat = (sessionId: string) => getJson<ChatDetail>(`/sessions/${sessionId}`);
export const listConversations = (limit = 50) => getJson<Conversation[]>(`/sessions?limit=${limit}`);
export const getTrace = (runId: string) => getJson<Trace>(`/runs/${runId}/trace`);
