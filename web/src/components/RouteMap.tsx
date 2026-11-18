"use client";

import { useEffect, useRef, useState } from "react";

import type { CommuteLeg, RoutePlace } from "@/lib/api";

/** A home's commute drawn along its real path: each leg from OpenTripPlanner (walk, bus 91B, the MTR
 *  line) over Stadia Maps' dark tiles (OpenStreetMap data), as plain tiles and an SVG overlay, so five
 *  cards cost a few small images each, not five WebGL maps. Only journeys with leg paths are drawn: a
 *  straight line between stops would read as a route that is not one. Stadia serves localhost
 *  without a key; a deployed site needs a free Stadia account with its domain registered. */

const TILE = 256;
const PAD = 26;
const TILE_URL = (z: number, x: number, y: number) =>
  `https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/${z}/${x}/${y}@2x.png`;

const MODE_COLOUR: Record<string, string> = {
  walk: "rgb(255 255 255 / 0.55)",
  bus: "var(--amber)",
  minibus: "var(--ok)",
  mtr: "var(--sky)",
  tram: "var(--teal)",
  ferry: "var(--teal)",
};

/** Web Mercator: degrees -> world pixels at zoom z. */
function project(lat: number, lon: number, z: number): [number, number] {
  const scale = TILE * 2 ** z;
  const s = Math.sin((lat * Math.PI) / 180);
  return [((lon + 180) / 360) * scale, (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * scale];
}

function fitZoom(points: [number, number][], w: number, h: number): number {
  for (let z = 16; z >= 9; z--) {
    const pts = points.map(([lat, lon]) => project(lat, lon, z));
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => p[1]);
    if (Math.max(...xs) - Math.min(...xs) <= w - 2 * PAD && Math.max(...ys) - Math.min(...ys) <= h - 2 * PAD) return z;
  }
  return 9;
}

const colourOf = (leg: CommuteLeg) => (leg.color ? `#${leg.color}` : (MODE_COLOUR[leg.mode] ?? "var(--amber)"));

/** Only real paths are drawn. */
export const hasRealPath = (legs: CommuteLeg[]) => legs.some((l) => l.mode !== "walk" && (l.path?.length ?? 0) >= 2);

type Props = { legs: CommuteLeg[]; route: RoutePlace[]; approximate?: boolean; height?: number };

export function RouteMap({ legs, route, approximate = false, height = 168 }: Props) {
  const box = useRef<HTMLAnchorElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const home = route.find((p) => p.kind === "home");
  const campus = route.find((p) => p.kind === "campus");
  const href =
    home && campus
      ? `https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=${home.lat}%2C${home.lon}%3B${campus.lat}%2C${campus.lon}`
      : undefined;

  const points: [number, number][] = [
    ...legs.flatMap((l) => l.path ?? []),
    ...route.map((p) => [p.lat, p.lon] as [number, number]),
  ];

  let body = null;
  if (width > 0 && points.length >= 2) {
    const z = fitZoom(points, width, height);
    const world = points.map(([lat, lon]) => project(lat, lon, z));
    const xs = world.map((p) => p[0]);
    const ys = world.map((p) => p[1]);
    const ox = (Math.min(...xs) + Math.max(...xs)) / 2 - width / 2; // world pixel at the box's top-left
    const oy = (Math.min(...ys) + Math.max(...ys)) / 2 - height / 2;
    const at = (lat: number, lon: number) => {
      const [x, y] = project(lat, lon, z);
      return [x - ox, y - oy] as const;
    };
    const tiles = [];
    for (let tx = Math.floor(ox / TILE); tx <= Math.floor((ox + width) / TILE); tx++) {
      for (let ty = Math.floor(oy / TILE); ty <= Math.floor((oy + height) / TILE); ty++) {
        tiles.push(
          // eslint-disable-next-line @next/next/no-img-element -- raw map tiles, positioned by hand
          <img
            key={`${tx}/${ty}`}
            src={TILE_URL(z, tx, ty)}
            alt=""
            loading="lazy"
            width={TILE}
            height={TILE}
            className="absolute max-w-none"
            style={{ left: tx * TILE - ox, top: ty * TILE - oy }}
          />,
        );
      }
    }
    const stops = route.filter((p) => p.kind === "board" || p.kind === "alight" || p.kind === "station");
    const ends = route.filter((p) => p.kind === "home" || p.kind === "campus");
    body = (
      <>
        {tiles}
        <svg className="absolute inset-0" width={width} height={height} aria-hidden>
          {legs.map((leg, i) =>
            (leg.path?.length ?? 0) >= 2 ? (
              <polyline
                key={i}
                points={leg.path!.map(([lat, lon]) => at(lat, lon).join(",")).join(" ")}
                fill="none"
                stroke={colourOf(leg)}
                strokeWidth={leg.mode === "walk" ? 2 : 4}
                strokeDasharray={leg.mode === "walk" ? "2 5" : undefined}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ) : null,
          )}
          {stops.map((p, i) => {
            const [x, y] = at(p.lat, p.lon);
            return <circle key={`s${i}`} cx={x} cy={y} r={3.5} fill="var(--bg)" stroke="var(--fg)" strokeWidth={2} />;
          })}
          {ends.map((p) => {
            const [x, y] = at(p.lat, p.lon);
            const colour = p.kind === "home" ? "#ff7a45" : "var(--sky)";
            return (
              <g key={p.kind}>
                {p.kind === "home" && approximate ? (
                  <circle cx={x} cy={y} r={16} fill="none" stroke="#ff7a45" strokeOpacity={0.6} strokeDasharray="3 3" />
                ) : null}
                <circle cx={x} cy={y} r={7} fill={colour} stroke="#fff" strokeWidth={2.5} />
              </g>
            );
          })}
        </svg>
        {ends.map((p) => {
          const [x, y] = at(p.lat, p.lon);
          return (
            <span
              key={p.kind}
              className="absolute -translate-x-1/2 rounded-md bg-bg/85 px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap text-fg"
              style={{ left: x, top: y + 11 }}
            >
              {p.kind === "home" ? (approximate ? "Home (approx.)" : "Home") : p.name}
            </span>
          );
        })}
      </>
    );
  }

  return (
    <a
      ref={box}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title="Open in OpenStreetMap"
      className="relative block overflow-hidden rounded-xl bg-raised ring-1 ring-line-faint"
      style={{ height }}
    >
      {body}
      <span className="absolute right-1.5 bottom-1 rounded bg-bg/70 px-1 text-[9px] text-faint">
        © Stadia Maps © OpenMapTiles © OpenStreetMap
      </span>
    </a>
  );
}
