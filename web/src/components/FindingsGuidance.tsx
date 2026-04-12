import type { FindingGroupCardProps } from "@/components/FindingGroupCard";
import { priorityBucketForReviewType } from "@/lib/reviewClaimsDisplay";

type StepState = "done" | "current" | "upcoming";

function StepPill({ state, label, step }: { state: StepState; label: string; step: number }) {
  const ring =
    state === "current"
      ? "border-zinc-500/45 bg-zinc-500/[0.1] text-lab-text"
      : state === "done"
        ? "border-emerald-500/30 bg-emerald-500/[0.08] text-emerald-100/95"
        : "border-white/[0.08] bg-white/[0.03] text-lab-muted";

  return (
    <li className="flex min-w-0 flex-1 flex-col items-center gap-1.5 text-center sm:items-stretch">
      <div
        className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-left text-sm font-medium leading-snug ${ring}`}
      >
        <span className="text-[10px] font-semibold tabular-nums text-lab-subtle">{step}</span>
        <span className="min-w-0 flex-1">{label}</span>
      </div>
      {state === "current" ? (
        <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-400">You are here</span>
      ) : (
        <span className="text-[10px] text-transparent"> </span>
      )}
    </li>
  );
}

/** Three-beat summary: organized → review → strategy (retail findings step). */
export function FindingsStepSummary() {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-lab-surface/90 px-4 py-5 sm:px-5">
      <p className="mb-3 text-center text-[11px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
        What happens next
      </p>
      <ol className="flex flex-col gap-3 sm:flex-row sm:gap-2">
        <StepPill state="done" step={1} label="Findings organized" />
        <StepPill state="current" step={2} label="Review your list" />
        <StepPill state="upcoming" step={3} label="Strategy built next" />
      </ol>
      <p className="mx-auto mt-4 max-w-prose text-center text-xs leading-relaxed text-lab-muted">
        One step at a time: finish review here — nothing is disputed until you confirm your list. Strategy
        comes after.
      </p>
    </div>
  );
}

const BUCKET_HEADLINE: Record<"review_first" | "verify_carefully" | "lower_priority", string> = {
  review_first: "Review first",
  verify_carefully: "Verify carefully",
  lower_priority: "Probably lower priority",
};

const BUCKET_BLURB: Record<"review_first" | "verify_carefully" | "lower_priority", string> = {
  review_first: "Worth scanning before the rest — score and accuracy signals.",
  verify_carefully: "Take your time; match names, duplicates, and ownership.",
  lower_priority: "Still review — grouped so you can pace yourself.",
};

/** Maps existing categories into three priority columns (editorial only; same data). */
export function FindingsStartHerePanel({ groups }: { groups: FindingGroupCardProps[] }) {
  const reviewFirst: string[] = [];
  const verifyCarefully: string[] = [];
  const lower: string[] = [];

  for (const g of groups) {
    const rt = g.reviewType ?? "unknown";
    const bucket = priorityBucketForReviewType(rt);
    const line = `${g.title} · ${g.count} ${g.count === 1 ? "item" : "items"}`;
    if (bucket === "review_first") reviewFirst.push(line);
    else if (bucket === "verify_carefully") verifyCarefully.push(line);
    else lower.push(line);
  }

  const col = (
    key: "review_first" | "verify_carefully" | "lower_priority",
    lines: string[],
  ) => (
    <div className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-3">
      <p className="text-xs font-semibold text-lab-text">{BUCKET_HEADLINE[key]}</p>
      <p className="mt-1 text-[11px] leading-snug text-lab-muted">{BUCKET_BLURB[key]}</p>
      {lines.length ? (
        <ul className="mt-2 space-y-1.5 text-[13px] leading-snug text-lab-text/90">
          {lines.map((l) => (
            <li key={l} className="border-l-2 border-zinc-600/45 pl-2">
              {l}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-[13px] text-lab-muted">None in this bucket for your report.</p>
      )}
    </div>
  );

  return (
    <section
      className="rounded-2xl border border-zinc-700/45 bg-gradient-to-b from-white/[0.035] to-lab-surface/80 px-4 py-5 sm:px-5"
      aria-labelledby="findings-start-here"
    >
      <h2 id="findings-start-here" className="text-base font-semibold text-lab-text">
        Start here
      </h2>
      <p className="mt-1 max-w-prose text-sm leading-relaxed text-lab-muted">
        Your full list is below — this is only a suggested order so you don&apos;t have to read every card
        to know where to begin.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {col("review_first", reviewFirst)}
        {col("verify_carefully", verifyCarefully)}
        {col("lower_priority", lower)}
      </div>
    </section>
  );
}
