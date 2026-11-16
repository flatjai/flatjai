"use client";

import { ArrowSquareOut, Bed, CaretDown, Check, Question, Ruler, Train, X } from "@phosphor-icons/react";
import { useState } from "react";

import type { Card, Check as CheckT, CostItem } from "@/lib/api";
import { fetchedAgo, hkd } from "@/lib/format";

const CHECK_LABEL: Record<string, string> = {
  budget: "Budget",
  room: "Room",
  bedrooms: "Bedrooms",
  move_in: "Move-in",
  area: "Area",
  commute: "Commute",
};

const CHECK_STYLE = {
  ok: { icon: Check, cls: "bg-ok/10 text-ok" },
  bad: { icon: X, cls: "bg-bad/10 text-bad" },
  unknown: { icon: Question, cls: "bg-raised-2 text-muted" },
};

/** Hard limits checked in code: fits, fails, or not stated on the listing. Hover for the detail. */
function Checks({ checks }: { checks: CheckT[] }) {
  if (!checks.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {checks.map((c) => {
        const s = CHECK_STYLE[c.ok === true ? "ok" : c.ok === false ? "bad" : "unknown"];
        return (
          <li key={c.name} title={c.detail} className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs ${s.cls}`}>
            <s.icon size={12} weight="bold" />
            {CHECK_LABEL[c.name] ?? c.name}
          </li>
        );
      })}
    </ul>
  );
}

function Items({ items }: { items: CostItem[] }) {
  return (
    <ul className="flex flex-col gap-1">
      {items.map((i) => (
        <li key={i.label} className="flex justify-between gap-3 text-xs">
          <span className="text-muted">
            {i.label}
            {i.assumed ? <span className="text-faint"> *</span> : null}
          </span>
          <span className="tabular-nums text-fg">{hkd(i.hkd)}</span>
        </li>
      ))}
    </ul>
  );
}

type Props = { card: Card; rank?: number | null; reasons?: string[] };

export function ListingCard({ card, rank = null, reasons = [] }: Props) {
  const { listing: l, cost } = card;
  const [open, setOpen] = useState(false);
  const ev = l.evidence;
  const size = l.saleable_sqft ? `${l.saleable_sqft} ft²` : l.gross_sqft ? `${l.gross_sqft} ft² gross` : null;
  const beds = l.bedrooms === null ? null : l.bedrooms === 0 ? "Studio" : `${l.bedrooms} bed`;

  return (
    <article className="fj-arrive-glow flex flex-col gap-4 rounded-2xl bg-surface p-5">
      <header className="flex items-start gap-3">
        {rank ? (
          <span className="fj-sunset grid size-8 flex-none place-items-center rounded-full text-sm font-bold">
            {rank}
          </span>
        ) : null}
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[15px] font-semibold text-fg">{l.title}</h3>
          <p className="truncate text-sm text-muted">{[l.district, l.address].filter(Boolean).join(" · ") || "Hong Kong"}</p>
        </div>
      </header>

      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[28px] leading-none font-bold tracking-tight tabular-nums" title={ev.rent_hkd_month ? `From the page: “${ev.rent_hkd_month}”` : undefined}>
            {hkd(cost.monthly_hkd)}
            <span className="ml-1 text-sm font-normal whitespace-nowrap text-muted">/month all in</span>
          </p>
          <p className="mt-1.5 text-xs text-muted">
            rent {hkd(l.rent_hkd_month)} · {hkd(cost.move_in_hkd)} to move in
          </p>
        </div>
        <div className="flex flex-none gap-3 text-xs text-muted">
          {size ? (
            <span className="flex items-center gap-1" title={ev.saleable_sqft ?? ev.gross_sqft}>
              <Ruler size={14} weight="fill" className="text-faint" />
              {size}
            </span>
          ) : null}
          {beds ? (
            <span className="flex items-center gap-1" title={ev.bedrooms}>
              <Bed size={14} weight="fill" className="text-faint" />
              {beds}
            </span>
          ) : null}
        </div>
      </div>

      {card.commute ? (
        <p
          className="flex items-center gap-2 text-sm text-fg"
          title={card.commute.legs.map((l) => `${l.text}: ${Math.round(l.minutes)} min`).join("\n")}
        >
          <Train size={16} weight="fill" className="flex-none text-sky" />
          <span className="font-medium tabular-nums">~{card.commute.minutes} min</span>
          <span className="min-w-0 truncate text-muted">
            {card.commute.legs.map((l) => l.text).join(" → ")}
          </span>
          {card.commute.precision === "area" ? (
            <span className="flex-none text-xs text-faint" title="The building could not be placed; estimated from the district">
              (area)
            </span>
          ) : null}
        </p>
      ) : null}

      {reasons.length ? (
        <ul className="fj-sunset-soft flex flex-col gap-1.5 rounded-xl px-4 py-3 text-sm text-fg">
          {reasons.map((r) => (
            <li key={r} className="flex gap-2">
              <span className="fj-sunset mt-[7px] size-1.5 flex-none rounded-full" />
              {r}
            </li>
          ))}
        </ul>
      ) : null}

      <Checks checks={card.checks} />

      {open ? (
        <div className="fj-rise grid gap-4 rounded-xl bg-raised p-4 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-semibold text-fg">Every month</p>
            <Items items={cost.monthly_items} />
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold text-fg">At move-in</p>
            <Items items={cost.move_in_items} />
          </div>
          <p className="text-[11px] text-faint sm:col-span-2">* Hong Kong norm, not stated on the listing</p>
        </div>
      ) : null}

      <footer className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line-faint pt-3 text-xs">
        <a
          href={l.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 font-medium text-coral-strong hover:text-coral"
        >
          View on {l.portal}
          <ArrowSquareOut size={13} weight="bold" />
        </a>
        <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-muted hover:text-fg">
          Costs
          <CaretDown size={12} weight="bold" className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        <span className="ml-auto text-faint">price read {fetchedAgo(card.fetched_at)}</span>
      </footer>
    </article>
  );
}

/** A card still being read: the real card's geometry, so nothing jumps when it arrives. */
export function ListingCardSkeleton() {
  return (
    <div className="flex flex-col gap-4 rounded-2xl bg-surface p-5 ring-1 ring-line-faint" aria-hidden>
      <div className="flex flex-col gap-2">
        <span className="fj-skeleton h-4 w-[58%]" />
        <span className="fj-skeleton h-3.5 w-[30%]" />
      </div>
      <div className="flex flex-col gap-2">
        <span className="fj-skeleton h-7 w-[42%]" />
        <span className="fj-skeleton h-3 w-[36%]" />
      </div>
      <div className="flex gap-1.5">
        <span className="fj-skeleton h-6 w-20 rounded-full" />
        <span className="fj-skeleton h-6 w-16 rounded-full" />
        <span className="fj-skeleton h-6 w-24 rounded-full" />
      </div>
    </div>
  );
}
