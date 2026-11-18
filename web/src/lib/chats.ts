// Client-side chat store: one shared list for every place that shows chats, and a cache of opened
// chats so switching between them, or back from the inspector, needs no request at all.
import { useSyncExternalStore } from "react";

import { getChat, listConversations, type ChatDetail, type Conversation } from "./api";
import { SETTLED_RUNS } from "./run-state";

// the list ------------------------------------------------------------------------------------

type ListState = { chats: Conversation[] | null; fetchedAt: number };
let list: ListState = { chats: null, fetchedAt: 0 };
let listInFlight: Promise<void> | null = null;
const listeners = new Set<() => void>();

function emit() {
  for (const l of listeners) l();
}

/** Fetch the chat list once, however many components ask at the same moment. */
export function refreshChats(): Promise<void> {
  listInFlight ??= listConversations()
    .then(
      (cs) => {
        list = { chats: [...cs].sort((a, b) => b.last_at.localeCompare(a.last_at)), fetchedAt: Date.now() };
      },
      () => {
        list = { chats: list.chats ?? [], fetchedAt: Date.now() };
      },
    )
    .finally(() => {
      listInFlight = null;
      emit();
    });
  return listInFlight;
}

function subscribe(l: () => void) {
  listeners.add(l);
  if (!list.chats && !listInFlight) void refreshChats();
  return () => listeners.delete(l);
}

const NO_CHATS: ListState = { chats: null, fetchedAt: 0 };

export function useChatList(): ListState {
  return useSyncExternalStore(
    subscribe,
    () => list,
    () => NO_CHATS,
  );
}

// one chat ------------------------------------------------------------------------------------

const cache = new Map<string, ChatDetail>();
const inFlight = new Map<string, Promise<ChatDetail>>();

const settled = (c: ChatDetail) => c.runs.every((r) => SETTLED_RUNS.has(r.status));

/** A chat already in hand, if any: the page can show it in the same frame. */
export const peekChat = (sessionId: string) => cache.get(sessionId) ?? null;

/** Load a chat (one request, shared by concurrent callers). Settled chats stay cached; a chat
 *  with a turn still running is fetched fresh each time. */
export function loadChat(sessionId: string): Promise<ChatDetail> {
  const hit = cache.get(sessionId);
  if (hit) return Promise.resolve(hit);
  let p = inFlight.get(sessionId);
  if (!p) {
    p = getChat(sessionId)
      .then((chat) => {
        if (settled(chat)) cache.set(sessionId, chat);
        return chat;
      })
      .finally(() => inFlight.delete(sessionId));
    inFlight.set(sessionId, p);
  }
  return p;
}

/** Warm the cache (on hover, before the click lands). */
export function prefetchChat(sessionId: string) {
  if (!cache.has(sessionId) && !inFlight.has(sessionId)) loadChat(sessionId).catch(() => undefined);
}

/** A chat changed (a new turn started or settled): the next open fetches it again. */
export function forgetChat(sessionId: string | null) {
  if (sessionId) cache.delete(sessionId);
}

// navigation ----------------------------------------------------------------------------------

/** Move between chats on the same page without a server round trip: Next keeps useSearchParams in
 *  step with the History API. */
export function goToChat(sessionId: string | null, { replace = false } = {}) {
  const url = sessionId ? `/?c=${sessionId}` : "/";
  if (replace) window.history.replaceState(null, "", url);
  else window.history.pushState(null, "", url);
}
