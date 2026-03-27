import type { TrackingContextPayload } from "@/lib/trackingTypes";

export function TrackingTruthStatusCard({
  tracking,
}: {
  tracking: TrackingContextPayload;
}) {
  const ts = tracking.trackingStatus;
  if (!ts) return null;
  return (
    <section
      className="mx-auto mt-5 max-w-sm rounded-xl border border-white/[0.1] bg-lab-surface px-4 py-4 sm:px-5"
      aria-labelledby="tracking-truth-title"
    >
      <h2
        id="tracking-truth-title"
        className="text-[15px] font-semibold leading-snug text-lab-text sm:text-base"
      >
        {ts.title}
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">{ts.message}</p>
    </section>
  );
}
