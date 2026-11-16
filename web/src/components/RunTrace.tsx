"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { getTrace, type Span, type Trace } from "@/lib/api";

const KIND_COLOUR: Record<Span["kind"], string> = {
  stage: "bg-accent/30",
  model: "bg-accent",
  tool: "bg-warn/70",
};

type Row = { span: Span; depth: number; offset: number };

/** Spans in tree order (each stage followed by its children), with start offsets in ms. */
function rows(spans: Span[]): { rows: Row[]; total: number } {
  if (!spans.length) return { rows: [], total: 0 };
  const t0 = Math.min(...spans.map((s) => Date.parse(s.started_at)));
  const end = Math.max(...spans.map((s) => Date.parse(s.started_at) + s.ms));
  const children = new Map<string | null, Span[]>();
  for (const s of spans) {
    const key = s.parent_id && spans.some((p) => p.id === s.parent_id) ? s.parent_id : null;
    children.set(key, [...(children.get(key) ?? []), s]);
  }
  const out: Row[] = [];
  const walk = (parent: string | null, depth: number) => {
    for (const s of (children.get(parent) ?? []).sort((a, b) => a.started_at.localeCompare(b.started_at))) {
      out.push({ span: s, depth, offset: Date.parse(s.started_at) - t0 });
      walk(s.id, depth + 1);
    }
  };
  walk(null, 0);
  return { rows: out, total: end - t0 };
}

function label(s: Span): string {
  const a = s.attrs;
  if (s.name === "fetch" || s.name === "search") {
    const target = String(a.url ?? a.query ?? "");
    return `${s.name} ${a.cache === "hit" ? "(cache) " : ""}${decodeURIComponent(target.replace(/^https?:\/\/[^/]+/, ""))}`;
  }
  if (s.name === "decide") return `decide: ${a.decision ?? ""}${a.forced ? ` (${a.forced})` : ""}`;
  return s.name;
}

const secs = (ms: number) => `${(ms / 1000).toFixed(ms < 10000 ? 1 : 0)}s`;

export function RunTrace() {
  const { id } = useParams<{ id: string }>();
  const [trace, setTrace] = useState<Trace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    getTrace(id).then(setTrace, (e) => setError(String(e)));
  }, [id]);

  const view = useMemo(() => rows(trace?.spans ?? []), [trace]);
  const model = trace?.totals.model;
  const errors = trace?.spans.filter((s) => s.error).length ?? 0;
  const cacheHits = trace?.spans.filter((s) => s.attrs.cache === "hit").length ?? 0;

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-col gap-5 px-4 py-10">
      <header className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-bold">Run {id}</h1>
        <Link href="/runs" className="text-sm text-accent hover:underline">
          ← all runs
        </Link>
      </header>
      {error ? <p className="text-warn">{error}</p> : null}
      {trace ? (
        <>
          <section className="flex flex-col gap-1 text-sm">
            <p className="font-medium">“{trace.run.brief}”</p>
            <p className="text-muted tabular-nums">
              {trace.run.status} · {trace.run.model} · {secs(view.total)} · {model?.count ?? 0} model calls (
              {model?.tokens_in ?? 0} in / {model?.tokens_out ?? 0} out tokens) · {trace.totals.tool?.count ?? 0} tool
              calls ({cacheHits} cache hits) · {errors} errors
            </p>
          </section>

          <div className="flex gap-4 text-xs text-muted">
            {(["stage", "model", "tool"] as const).map((k) => (
              <span key={k} className="flex items-center gap-1.5">
                <span className={`inline-block h-2.5 w-4 rounded-sm ${KIND_COLOUR[k]}`} />
                {k}
              </span>
            ))}
          </div>

          <ol className="flex flex-col overflow-hidden rounded-2xl border border-line bg-surface text-xs">
            {view.rows.map(({ span: s, depth, offset }) => (
              <li key={s.id} className="border-b border-line last:border-0">
                <button
                  onClick={() => setOpen(open === s.id ? null : s.id)}
                  className="grid w-full grid-cols-[minmax(0,2fr)_minmax(0,3fr)_4.5rem] items-center gap-2 px-3 py-1.5 text-left hover:bg-bg"
                >
                  <span className="truncate" style={{ paddingLeft: depth * 12 }}>
                    <span className={s.error ? "text-warn" : s.kind === "stage" ? "font-semibold" : ""}>{label(s)}</span>
                  </span>
                  <span className="relative h-3 rounded bg-line/40">
                    <span
                      className={`absolute top-0 h-3 rounded ${KIND_COLOUR[s.kind]} ${s.error ? "ring-1 ring-warn" : ""}`}
                      style={{
                        left: `${(offset / view.total) * 100}%`,
                        width: `max(2px, ${(s.ms / view.total) * 100}%)`,
                      }}
                    />
                  </span>
                  <span className="text-right tabular-nums text-muted">{secs(s.ms)}</span>
                </button>
                {open === s.id ? (
                  <div className="flex flex-col gap-2 bg-bg px-3 py-3">
                    <p className="text-muted tabular-nums">
                      {s.kind} · started +{secs(offset)} · {s.ms.toFixed(0)} ms
                      {s.tokens_in ? ` · ${s.tokens_in} in / ${s.tokens_out} out tokens` : ""}
                      {typeof s.attrs.queue_ms === "number" ? ` · waited ${secs(s.attrs.queue_ms)} for the model` : ""}
                    </p>
                    {s.error ? <p className="text-warn">{s.error}</p> : null}
                    <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface p-3 text-[11px] leading-relaxed">
                      {JSON.stringify(s.attrs, null, 2)}
                    </pre>
                  </div>
                ) : null}
              </li>
            ))}
          </ol>
        </>
      ) : null}
    </main>
  );
}
