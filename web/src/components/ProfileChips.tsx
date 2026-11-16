import type { Profile } from "@/lib/api";
import { hkd, monthYear } from "@/lib/format";

const MISSING_LABEL: Record<string, string> = {
  budget_hkd_month: "budget",
  campus: "campus",
  move_in: "move-in date",
};

/** What the agent understood from the brief, so the student can catch a misreading early. */
export function ProfileChips({ profile, missing }: { profile: Profile; missing: string[] }) {
  const chips: string[] = [];
  if (profile.budget_hkd_month)
    chips.push(`≤ ${hkd(profile.budget_hkd_month)}/month${profile.budget_is_total ? " in total" : ""}`);
  if (profile.flatmates) chips.push(`sharing with ${profile.flatmates}`);
  if (profile.campus) chips.push(profile.max_commute_min ? `≤ ${profile.max_commute_min} min to ${profile.campus}` : `near ${profile.campus}`);
  if (profile.room_only === true) chips.push("room in a shared flat");
  if (profile.room_only === false) chips.push(profile.bedrooms ? `${profile.bedrooms}-bedroom flat` : "whole flat");
  if (profile.move_in) chips.push(`from ${monthYear(profile.move_in)}`);
  chips.push(...profile.districts.map((d) => `in ${d}`));
  chips.push(...profile.soft_preferences);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((c) => (
        <span key={c} className="rounded-full bg-coral-soft px-2.5 py-1 text-xs font-medium text-coral-strong">
          {c}
        </span>
      ))}
      {missing.map((m) => (
        <span key={m} className="rounded-full border border-dashed border-warn/60 px-2.5 py-1 text-xs text-warn">
          no {MISSING_LABEL[m] ?? m} given
        </span>
      ))}
    </div>
  );
}
