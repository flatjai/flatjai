"use client";

import { useEffect, useRef, useState } from "react";

/** Jai, FlatJai's character: a small sunset-coloured house with eyes, the "little flat-finder" (揾樓仔).
 *
 *  Mood follows what the agent is doing. With `follow`, Jai is interactive: its eyes and head track
 *  the pointer, it looks at the text box and nods while you type, widens its eyes on hover, squishes
 *  when tapped, and dozes off when left alone. `celebrate` (a counter) makes it hop with joy each
 *  time it changes, e.g. when a home that fits arrives.
 *
 *  Eye tracking writes CSS variables straight onto the SVG (no React re-render per pointer move). */
export type JaiMood = "idle" | "thinking" | "reading" | "happy" | "curious" | "sad" | "excited";

type Props = {
  mood?: JaiMood;
  size?: number;
  className?: string;
  follow?: boolean;
  celebrate?: number;
  sleepAfterMs?: number;
};

const MAX_LOOK = 2.6; // svg units the pupils may travel
const MAX_TILT = 5; // degrees the head turns toward the pointer

export function Jai({
  mood = "idle",
  size = 40,
  className = "",
  follow = false,
  celebrate = 0,
  sleepAfterMs = 20000,
}: Props) {
  const svg = useRef<SVGSVGElement>(null);

  const [flash, setFlash] = useState<"happy" | "boop" | null>(null);
  const [sleepy, setSleepy] = useState(false);

  // a hop of joy whenever `celebrate` changes (timers, so no synchronous state change in the effect)
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const on = setTimeout(() => setFlash("happy"), 0);
    const off = setTimeout(() => setFlash(null), 1300);
    return () => {
      clearTimeout(on);
      clearTimeout(off);
    };
  }, [celebrate]);

  // interactive eyes: follow the pointer, look at the focused text box, nod while typing, doze when idle
  useEffect(() => {
    const el = svg.current;
    if (!follow || !el) return;
    let sleepTimer = 0;
    let nodTimer = 0;
    const wake = () => {
      setSleepy(false);
      clearTimeout(sleepTimer);
      sleepTimer = window.setTimeout(() => setSleepy(true), sleepAfterMs);
    };
    const lookAt = (x: number, y: number) => {
      const r = el.getBoundingClientRect();
      const dx = x - (r.left + r.width / 2);
      const dy = y - (r.top + r.height * 0.58);
      const dist = Math.hypot(dx, dy) || 1;
      const reach = Math.min(dist / 140, 1); // close to Jai: small moves; far away: full reach
      el.style.setProperty("--px", `${((dx / dist) * MAX_LOOK * reach).toFixed(2)}px`);
      el.style.setProperty("--py", `${((dy / dist) * MAX_LOOK * reach).toFixed(2)}px`);
      el.style.setProperty("--tilt", `${(Math.max(-1, Math.min(1, dx / 400)) * MAX_TILT).toFixed(2)}deg`);
    };
    const onPointer = (e: PointerEvent) => {
      wake();
      lookAt(e.clientX, e.clientY);
    };
    const onTyping = () => {
      wake();
      const box = document.activeElement?.getBoundingClientRect();
      if (box) lookAt(box.left + Math.min(box.width * 0.35, 220), box.top + box.height / 2);
      el.dataset.nod = "";
      clearTimeout(nodTimer);
      nodTimer = window.setTimeout(() => delete el.dataset.nod, 260);
    };
    wake();
    window.addEventListener("pointermove", onPointer, { passive: true });
    window.addEventListener("pointerdown", onPointer, { passive: true });
    window.addEventListener("fj:typing", onTyping);
    return () => {
      clearTimeout(sleepTimer);
      clearTimeout(nodTimer);
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("fj:typing", onTyping);
    };
  }, [follow, sleepAfterMs]);

  const boop = () => {
    if (!follow) return;
    setFlash("boop");
    setTimeout(() => setFlash(null), 900);
  };

  const shown: JaiMood = flash ? "happy" : mood;
  const happy = shown === "happy";
  const wide = shown === "excited";
  return (
    <svg
      ref={svg}
      viewBox="0 0 64 64"
      width={size}
      height={size}
      className={`jai ${className}`}
      data-mood={shown}
      data-follow={follow ? "" : undefined}
      data-sleepy={follow && sleepy && !flash && mood === "idle" ? "" : undefined}
      data-flash={flash ?? undefined}
      onClick={boop}
      role="img"
      aria-label={`Jai, ${sleepy ? "dozing" : shown}`}
    >
      <defs>
        <linearGradient id="jai-sunset" x1="0.15" y1="0" x2="0.85" y2="1">
          <stop offset="0" stopColor="#ffc24d" />
          <stop offset="0.55" stopColor="#ff7a45" />
          <stop offset="1" stopColor="#ff4f4f" />
        </linearGradient>
      </defs>
      <g className="jai-figure" key={celebrate}>
        <rect x="41" y="9" width="8" height="14" rx="2.5" fill="#f2653a" />
        <path
          d="M32 7 L56 26 L56 51 Q56 57 50 57 L14 57 Q8 57 8 51 L8 26 Z"
          fill="url(#jai-sunset)"
          stroke="url(#jai-sunset)"
          strokeWidth="5"
          strokeLinejoin="round"
        />
        <path d="M14 27 L32 12.5 L50 27" fill="none" stroke="#fff" strokeOpacity="0.3" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <ellipse className="jai-cheek" cx="17.5" cy="46" rx="3.6" ry="2.4" fill="#ffd8c8" opacity="0.6" />
        <ellipse className="jai-cheek" cx="46.5" cy="46" rx="3.6" ry="2.4" fill="#ffd8c8" opacity="0.6" />

        {happy ? (
          <g fill="none" stroke="#2a120c" strokeWidth="3" strokeLinecap="round">
            <path d="M19.5 38.5 Q24 33 28.5 38.5" />
            <path d="M35.5 38.5 Q40 33 44.5 38.5" />
          </g>
        ) : (
          <g className="jai-eyes">
            <ellipse cx="24" cy="37" rx="5.6" ry={wide ? 7.2 : 6.4} fill="#fff" />
            <ellipse cx="40" cy="37" rx="5.6" ry={wide ? 7.2 : 6.4} fill="#fff" />
            <g className="jai-pupils" fill="#2a120c">
              <circle cx="24" cy="38" r={wide ? 3.4 : 3} />
              <circle cx="40" cy="38" r={wide ? 3.4 : 3} />
              <circle cx="25.2" cy="36.6" r="1" fill="#fff" />
              <circle cx="41.2" cy="36.6" r="1" fill="#fff" />
            </g>
          </g>
        )}

        {happy ? (
          <path d="M26.5 46 Q32 53.5 37.5 46 Z" fill="#2a120c" />
        ) : shown === "sad" ? (
          <path d="M28 50 Q32 46.5 36 50" fill="none" stroke="#2a120c" strokeWidth="2.4" strokeLinecap="round" />
        ) : shown === "curious" || wide ? (
          <ellipse cx="32" cy="48.5" rx="2.2" ry={wide ? 2.8 : 2.2} fill="#2a120c" />
        ) : (
          <path d="M28 47 Q32 50.5 36 47" fill="none" stroke="#2a120c" strokeWidth="2.4" strokeLinecap="round" />
        )}
      </g>
    </svg>
  );
}
