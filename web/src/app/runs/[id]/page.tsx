import { Suspense } from "react";

import { RunTrace } from "@/components/RunTrace";

// The trace view reads the run id with useParams(), a runtime value: Suspense lets the shell
// prerender and the trace stream in (Next 16 "blocking-prerender-client-hook").
export default function RunTracePage() {
  return (
    <Suspense fallback={<p className="px-4 py-10 text-muted">Loading run…</p>}>
      <RunTrace />
    </Suspense>
  );
}
