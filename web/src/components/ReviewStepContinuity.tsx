/**
 * Shared Step 2 review-phase framing for /analyze and /prepare.
 * Presentation only — no routing or data logic.
 */

type ReviewPhase = "analyze" | "prepare";

export function ReviewPhaseProgressStrip({ phase }: { phase: ReviewPhase }) {
  return (
    <div className="surface-where-fits mx-auto mt-6 max-w-2xl">
      <p className="text-center text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
        Where this fits
      </p>
      <ol className="mt-3 flex flex-col gap-2 text-sm sm:mt-4 sm:flex-row sm:justify-center sm:gap-3 sm:text-[13px]">
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted">
          <span className="font-semibold text-emerald-200/95">1.</span>
          <span className="ml-1.5">Upload completed</span>
        </li>
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text">
          <span className="text-lab-accent">2.</span>
          <span className="ml-1.5">Review and confirm</span>
        </li>
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted">
          <span className="text-lab-subtle">3.</span>
          <span className="ml-1.5">Strategy next</span>
        </li>
      </ol>
      <p className="mt-3 text-center text-xs leading-relaxed text-lab-muted">
        {phase === "analyze"
          ? "You're reviewing what we organized for your round."
          : "You're confirming what belongs in your round before strategy."}
      </p>
    </div>
  );
}

export function ReviewReassuranceBlock() {
  return (
    <div className="surface-emerald-reassure mx-auto mt-6 max-w-md text-left">
      <ul className="space-y-2 text-sm leading-relaxed text-lab-muted">
        <li className="flex gap-2">
          <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
          <span>This is part of preparing your round</span>
        </li>
        <li className="flex gap-2">
          <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
          <span>Nothing is disputed yet</span>
        </li>
        <li className="flex gap-2">
          <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
          <span>You will confirm before moving forward</span>
        </li>
      </ul>
    </div>
  );
}
