// What Jai can already pick up from a brief while the student types: a light, client-side hint so
// the student sees what is missing before sending. The real reading happens on the server
// (Understand stage, numbers grounded in the text); this only mirrors its simplest rules.

export type Hints = { budget: string | null; campus: string | null; moveIn: string | null; commute: string | null };

const CAMPUSES: [RegExp, string][] = [
  [/\bhkust\b|科大|科技大學/i, "HKUST"],
  [/\bhku\b|港大|香港大學/i, "HKU"],
  [/\bcuhk\b|中大|中文大學/i, "CUHK"],
  [/\bcity\s?u\b|城大|城市大學/i, "CityU"],
  [/\bpoly\s?u\b|理大|理工大學/i, "PolyU"],
  [/\bhkbu\b|浸大|浸會大學/i, "HKBU"],
  [/\bedu\s?hk\b|教大/i, "EdUHK"],
  [/\blingnan\b|嶺大/i, "Lingnan"],
];

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const CN_MONTH = /(十[一二]|[一二三四五六七八九十])月/;
const CN_DIGIT: Record<string, number> = { 一: 1, 二: 2, 兩: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10 };

function budget(text: string): string | null {
  const minutes = new Set([...text.matchAll(/(\d+)\s*(?:min|mins|minutes|分鐘)/gi)].map((m) => Number(m[1])));
  for (const m of text.matchAll(/(HK\$|\$)?\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(k\b|K\b|千|萬|万)?/g)) {
    const scale = m[3] ? (/[萬万]/.test(m[3]) ? 10000 : 1000) : 1;
    const value = Math.round(Number(m[2].replace(/,/g, "")) * scale);
    if (value >= 1000 && value <= 200000 && !minutes.has(value)) return `HK$${value.toLocaleString("en-HK")}`;
  }
  const cn = text.match(/([一二兩三四五六七八九])\s*(千|萬)/);
  if (cn) return `HK$${(CN_DIGIT[cn[1]] * (cn[2] === "萬" ? 10000 : 1000)).toLocaleString("en-HK")}`;
  return null;
}

function moveIn(text: string): string | null {
  for (const [i, name] of MONTHS.entries()) {
    if (new RegExp(`\\b${name.slice(0, 3)}(?:${name.slice(3)})?\\b`, "i").test(text)) return name;
    if (i === 8 && /\bsept\b/i.test(text)) return name;
  }
  const cn = text.match(CN_MONTH);
  if (cn) return MONTHS[(cn[1].length === 2 ? 10 + CN_DIGIT[cn[1][1]] : CN_DIGIT[cn[1]]) - 1];
  if (/\b(asap|now|immediately|next month)\b|即時|下個月/i.test(text)) return text.match(/next month|下個月/i) ? "next month" : "as soon as possible";
  return null;
}

export function hintsFrom(text: string): Hints {
  const minutes = text.match(/(\d+)\s*(?:min|mins|minutes|分鐘)/i);
  return {
    budget: budget(text),
    campus: CAMPUSES.find(([re]) => re.test(text))?.[1] ?? null,
    moveIn: moveIn(text),
    commute: minutes ? `${minutes[1]} min` : null,
  };
}

/** Budget, campus and move-in are the hard limits Jai would otherwise ask about. */
export const complete = (h: Hints) => Boolean(h.budget && h.campus && h.moveIn);
