"use client";

import { ChatsCircle, NotePencil, X } from "@phosphor-icons/react";
import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";

import type { Conversation } from "@/lib/api";
import { goToChat, prefetchChat, useChatList } from "@/lib/chats";

/** Previous chats as quiet text on the dark page: they step back until the pointer finds them. */

const DAY = 86_400_000;

function groupOf(iso: string, now: number): string {
  const startOfToday = new Date(now).setHours(0, 0, 0, 0);
  const t = new Date(iso).getTime();
  if (t >= startOfToday) return "Today";
  if (t >= startOfToday - DAY) return "Yesterday";
  if (t >= startOfToday - 7 * DAY) return "Previous 7 days";
  return "Older";
}

/** A link to a chat on this page: a plain click switches in place (no server round trip, and the
 *  chat is usually cached already); a modified click still opens a new tab. */
function ChatLink({
  sessionId,
  onPick,
  className,
  title,
  current,
  children,
}: {
  sessionId: string | null;
  onPick?: () => void;
  className: string;
  title?: string;
  current?: boolean;
  children: ReactNode;
}) {
  const onClick = (e: MouseEvent) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    onPick?.();
    goToChat(sessionId);
  };
  return (
    <a
      href={sessionId ? `/?c=${sessionId}` : "/"}
      onClick={onClick}
      onPointerEnter={sessionId ? () => prefetchChat(sessionId) : undefined}
      onFocus={sessionId ? () => prefetchChat(sessionId) : undefined}
      title={title}
      aria-current={current ? "page" : undefined}
      className={className}
    >
      {children}
    </a>
  );
}

function Chats({
  activeId,
  onPick,
  newChat = true,
}: {
  activeId: string | null;
  onPick?: () => void;
  newChat?: boolean;
}) {
  // the time of the fetch dates the groups (Today, Yesterday…), so render stays pure
  const { chats, fetchedAt: now } = useChatList();
  const groups: { label: string; items: Conversation[] }[] = [];
  for (const c of chats ?? []) {
    const label = groupOf(c.last_at, now);
    if (groups.at(-1)?.label !== label) groups.push({ label, items: [] });
    groups.at(-1)!.items.push(c);
  }

  return (
    <nav aria-label="Previous chats" className="flex min-h-0 flex-1 flex-col">
      {newChat ? (
        <ChatLink
          sessionId={null}
          onPick={onPick}
          className="mx-2 mb-3 flex items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] text-muted transition-colors hover:bg-white/[0.04] hover:text-fg"
        >
          <NotePencil size={15} />
          New chat
        </ChatLink>
      ) : null}

      <div className="fj-chat-scroll min-h-0 flex-1 overflow-y-auto px-2 pb-6">
        {chats && !chats.length ? <p className="px-2.5 text-[13px] text-faint/70">No chats yet.</p> : null}
        {groups.map((g) => (
          <section key={g.label} className="mb-4">
            <h2 className="px-2.5 pb-1 text-[11px] font-medium text-faint/60">{g.label}</h2>
            <ul>
              {g.items.map((c) => {
                const active = c.session_id === activeId;
                const title = c.runs[0]?.brief ?? "Untitled chat";
                return (
                  <li key={c.session_id}>
                    <ChatLink
                      sessionId={c.session_id}
                      onPick={onPick}
                      title={title}
                      current={active}
                      className={`block truncate rounded-lg px-2.5 py-1.5 text-[13px] transition-colors ${
                        active ? "bg-white/[0.05] text-fg" : "text-faint hover:bg-white/[0.03] hover:text-fg"
                      }`}
                    >
                      {title}
                    </ChatLink>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </nav>
  );
}

/** Desktop: a fixed rail under the header. */
export function ChatRail({ activeId }: { activeId: string | null }) {
  return (
    <aside className="fj-rail hidden lg:flex">
      <Chats activeId={activeId} />
    </aside>
  );
}

/** Phone and tablet: the same list in a drawer from the left. */
export function ChatDrawer({
  open,
  onClose,
  activeId,
}: {
  open: boolean;
  onClose: () => void;
  activeId: string | null;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Previous chats">
      <button className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" onClick={onClose} aria-label="Close chats" />
      <div className="fj-drawer absolute inset-y-0 left-0 flex w-[min(80vw,300px)] flex-col bg-bg pt-[max(12px,env(safe-area-inset-top))] ring-1 ring-line-faint">
        <div className="flex items-center justify-between px-4 pb-2">
          <span className="text-[13px] font-medium text-muted">Chats</span>
          <button onClick={onClose} className="rounded-lg p-1.5 text-faint hover:text-fg" aria-label="Close">
            <X size={16} weight="bold" />
          </button>
        </div>
        <Chats activeId={activeId} onPick={onClose} />
      </div>
    </div>
  );
}

/** Homepage: a quiet "Chats" button top right; the list drops down beneath it. */
export function ChatMenu() {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  return (
    <div ref={root} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="true"
        className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm transition-colors hover:bg-raised hover:text-fg ${
          open ? "bg-raised text-fg" : "text-muted"
        }`}
      >
        <ChatsCircle size={16} weight="bold" />
        <span>Chats</span>
      </button>
      {open ? (
        <div className="fj-pop absolute top-full right-0 mt-2 flex max-h-[min(70vh,560px)] w-[min(320px,calc(100vw-32px))] flex-col rounded-2xl bg-surface/95 pt-3 shadow-2xl ring-1 ring-line backdrop-blur-xl">
          <Chats activeId={null} onPick={() => setOpen(false)} newChat={false} />
        </div>
      ) : null}
    </div>
  );
}
