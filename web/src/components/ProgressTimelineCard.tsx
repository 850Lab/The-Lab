import { motion } from "framer-motion";

const STEPS = [
  { dayLabel: "Day 0", title: "Sent", range: "Mailed to bureaus" },
  { dayLabel: "Days 1–7", title: "Received & processing", range: "Arrival & intake" },
  { dayLabel: "Days 8–30", title: "Under review", range: "Bureau review window" },
  { dayLabel: "Day 30", title: "Response expected", range: "Typical reply timeframe" },
] as const;

type Props = {
  /** From backend ``timeline.daysSinceFirstMail`` (0 until first mailed send exists). */
  dayCurrent: number;
  totalDays: number;
};

function stepState(index: number, d: number): "done" | "current" | "upcoming" {
  if (index === 0) {
    if (d > 0) return "done";
    if (d === 0) return "current";
    return "upcoming";
  }
  if (index === 1) {
    if (d < 1) return "upcoming";
    if (d <= 7) return "current";
    return "done";
  }
  if (index === 2) {
    if (d < 8) return "upcoming";
    if (d < 30) return "current";
    return "done";
  }
  return d >= 30 ? "current" : "upcoming";
}

export function ProgressTimelineCard({ dayCurrent, totalDays }: Props) {
  const d = Math.max(0, Math.min(totalDays, dayCurrent));
  return (
    <motion.section
      variants={{
        hidden: { opacity: 0, y: 16 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 shadow-lg shadow-black/15 sm:px-6 sm:py-6"
    >
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
          Your timeline
        </h3>
        <p className="text-sm font-medium text-lab-accent">
          Day {d} of {totalDays}
        </p>
      </div>

      <div className="relative mt-6 pl-2">
        <div
          className="absolute left-[11px] top-2 bottom-2 w-px bg-white/[0.08]"
          aria-hidden
        />
        <ul className="space-y-0">
          {STEPS.map((step, index) => {
            const state = stepState(index, d);
            return (
              <li key={step.title} className="relative flex gap-4 pb-7 last:pb-0">
                <div className="relative z-[1] flex shrink-0 flex-col items-center pt-0.5">
                  <span
                    className={`flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full border-2 ${
                      state === "done"
                        ? "border-emerald-400/70 bg-emerald-500/15 text-emerald-300"
                        : state === "current"
                          ? "border-lab-accent bg-lab-accent/15 text-lab-accent"
                          : "border-white/[0.12] bg-lab-elevated text-lab-subtle"
                    }`}
                  >
                    {state === "done" ? (
                      <svg
                        className="h-2.5 w-2.5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={3}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    ) : (
                      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
                    )}
                  </span>
                </div>
                <div className="min-w-0 pt-0">
                  <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                    {step.dayLabel}
                  </p>
                  <p className="mt-0.5 text-[15px] font-semibold text-lab-text">
                    {step.title}
                  </p>
                  <p className="mt-1 text-sm text-lab-muted">{step.range}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </motion.section>
  );
}
