export const hkd = (n: number) => `HK$${n.toLocaleString("en-HK")}`;

export function fetchedAgo(iso: string): string {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  return hours < 48 ? `${hours} h ago` : new Date(iso).toLocaleDateString("en-HK");
}

export function monthYear(iso: string): string {
  return new Date(iso).toLocaleDateString("en-HK", { month: "short", year: "numeric" });
}
