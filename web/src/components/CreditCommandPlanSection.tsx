import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import type { CreditCommandPlanAction, CreditCommandPlanPayload } from "@/lib/letterTypes";

export type CreditCommandPlanVariant = "letters" | "tracking";

type Props = {
  plan: CreditCommandPlanPayload | null;
  unavailableReason?: string | null;
  /** Letters = pre-send; tracking = post-send leverage + escalation paths */
  variant?: CreditCommandPlanVariant;
  /** Landing demo: summary chips + expandable day cards */
  layout?: "default" | "publicDemoExpandable";
  /** Shown under chips when layout is publicDemoExpandable (e.g. chosen scenario title) */
  scenarioHeadline?: string | null;
};

function CommandPlanActionCard({ action }: { action: CreditCommandPlanAction }) {
  return (
    <li className="rounded-lg border border-white/[0.06] bg-lab-surface/80 px-3 py-3 sm:px-4">
      <p className="text-sm font-semibold text-lab-text">{action.title}</p>
      <div className="mt-2.5 rounded-lg border border-lab-accent/25 bg-lab-accent/[0.06] px-3 py-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-lab-accent">
          Do this now
        </p>
        <p className="mt-1.5 text-sm leading-relaxed text-lab-text">{action.do_next}</p>
      </div>
      <p className="mt-2.5 text-xs leading-relaxed text-lab-muted sm:text-[13px]">
        <span className="font-medium text-lab-text/80">Why it matters:</span> {action.why}
      </p>
      {action.warning ? (
        <p className="mt-2 text-xs leading-relaxed text-amber-200/85">
          <span className="font-medium">Watch out:</span> {action.warning}
        </p>
      ) : null}
      {action.script ? (
        <details className="mt-3 rounded-md border border-white/[0.08] bg-black/20 px-2 py-2">
          <summary className="cursor-pointer text-xs font-semibold text-lab-muted">
            Call script — open when you are on the line
          </summary>
          <pre className="mt-2 whitespace-pre-wrap font-sans text-[11px] leading-relaxed text-lab-text/90">
            {action.script}
          </pre>
        </details>
      ) : null}
    </li>
  );
}

function EscalationPathsCard() {
  return (
    <div className="mt-6 rounded-lg border border-white/[0.1] bg-black/25 px-3 py-4 sm:px-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
        Escalation paths
      </p>
      <p className="mt-2 text-xs leading-relaxed text-lab-muted sm:text-[13px]">
        Use these when a bureau misses the timeline or sends an inadequate response — they are
        official channels, not venting.
      </p>
      <ul className="mt-3 space-y-3 text-sm text-lab-text">
        <li className="flex gap-2">
          <span className="mt-0.5 font-mono text-[11px] text-lab-accent">1</span>
          <span>
            <span className="font-medium">30+ days, weak or no outcome:</span> file a complaint with
            the CFPB using your certified-mail proof.{" "}
            <a
              href="https://www.consumerfinance.gov/complaint/"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-lab-accent hover:underline"
            >
              consumerfinance.gov/complaint
            </a>
          </span>
        </li>
        <li className="flex gap-2">
          <span className="mt-0.5 font-mono text-[11px] text-lab-accent">2</span>
          <span>
            <span className="font-medium">State leverage:</span> your state attorney general consumer
            protection unit often takes structured complaints — same documentation packet as the
            CFPB.
          </span>
        </li>
        <li className="flex gap-2">
          <span className="mt-0.5 font-mono text-[11px] text-lab-accent">3</span>
          <span>
            <span className="font-medium">In-app map:</span> walk through structured escalation
            options tied to your workflow.{" "}
            <Link to="/escalation" className="font-medium text-lab-accent hover:underline">
              Open escalation guide
            </Link>
          </span>
        </li>
        <li className="flex gap-2">
          <span className="mt-0.5 font-mono text-[11px] text-lab-accent">4</span>
          <span>
            <span className="font-medium">Paper trail:</span> log every bureau or furnisher reply
            under Responses so your next move is data-backed.{" "}
            <Link to="/responses" className="font-medium text-lab-accent hover:underline">
              Record a response
            </Link>
          </span>
        </li>
      </ul>
    </div>
  );
}

export function CreditCommandPlanSection({
  plan,
  unavailableReason,
  variant = "letters",
  layout = "default",
  scenarioHeadline,
}: Props) {
  const [open, setOpen] = useState(true);
  const [expandedDay, setExpandedDay] = useState<number | null>(null);

  if (!plan) {
    if (!unavailableReason) return null;
    return (
      <p className="mt-6 text-center text-xs text-lab-subtle">
        72-hour gameplan unavailable for this session.
      </p>
    );
  }

  const { total_issues, high_impact, score_damaging, quick_wins, days } = plan;

  if (layout === "publicDemoExpandable") {
    return (
      <section className="overflow-hidden rounded-xl border border-lab-accent/25 bg-gradient-to-b from-lab-accent/[0.07] to-transparent px-3 py-4 sm:px-4 sm:py-5">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-accent">
            Execution
          </p>
          <h3 className="mt-1 text-[15px] font-semibold text-lab-text sm:text-base">
            72-hour gameplan
          </h3>
          <p className="mt-2 text-sm font-medium leading-snug text-lab-text sm:text-[15px]">
            Here&apos;s what you can do right now
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-lab-muted sm:text-sm">
            Concrete moves tied to this scenario — same engine members use. Tap a day to see the full
            checklist.
          </p>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full border border-white/[0.1] bg-white/[0.04] px-2.5 py-0.5 text-[11px] font-medium text-lab-text">
            {total_issues} issue{total_issues === 1 ? "" : "s"} in play
          </span>
          <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-200/90">
            {high_impact} high impact
          </span>
          <span className="rounded-full border border-red-400/20 bg-red-500/10 px-2.5 py-0.5 text-[11px] font-medium text-red-200/85">
            {score_damaging} score-damaging
          </span>
          <span className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-200/85">
            {quick_wins} quick win{quick_wins === 1 ? "" : "s"}
          </span>
        </div>

        {scenarioHeadline ? (
          <p className="mt-3 rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2 text-xs leading-relaxed text-lab-muted">
            <span className="font-semibold text-lab-text">Scenario: </span>
            {scenarioHeadline}
          </p>
        ) : null}

        <div className="mt-4 grid grid-cols-3 gap-2">
          {days.map((day, di) => {
            const active = expandedDay === di;
            return (
              <button
                key={`${day.label}-${di}`}
                type="button"
                data-testid={`demo-gameplan-day-${di}`}
                onClick={() => setExpandedDay(active ? null : di)}
                className={`flex min-h-[4.25rem] flex-col items-center justify-center rounded-xl border px-2 py-2.5 text-center transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/40 ${
                  active
                    ? "border-lab-accent/50 bg-lab-accent/15 shadow-md shadow-lab-accent/10"
                    : "border-white/[0.1] bg-lab-surface/60 hover:border-white/[0.18] hover:bg-lab-surface/80"
                }`}
              >
                <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-lab-subtle">
                  {day.label}
                </span>
                <span className="mt-1 text-lg font-semibold tabular-nums text-lab-text">{di + 1}</span>
                <span className="mt-0.5 text-[10px] text-lab-muted">
                  {day.actions.length} move{day.actions.length === 1 ? "" : "s"}
                </span>
              </button>
            );
          })}
        </div>

        <AnimatePresence initial={false}>
          {expandedDay !== null && days[expandedDay] ? (
            <motion.div
              key={expandedDay}
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden"
            >
              <div className="mt-4 rounded-xl border border-lab-accent/20 bg-lab-bg/30 px-3 py-4 sm:px-4">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-lab-accent">
                  {days[expandedDay].label}
                </p>
                <ul className="mt-3 space-y-4">
                  {days[expandedDay].actions.map((action, ai) => (
                    <CommandPlanActionCard key={`${action.title}-${ai}`} action={action} />
                  ))}
                </ul>
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </section>
    );
  }

  const isTracking = variant === "tracking";

  return (
    <motion.section
      layout
      className="mt-10 overflow-hidden rounded-xl border border-lab-accent/25 bg-gradient-to-b from-lab-accent/[0.07] to-transparent px-4 py-4 sm:mt-11 sm:px-5 sm:py-5"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-start justify-between gap-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35"
        aria-expanded={open}
      >
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-accent">
            {isTracking ? "While mail moves" : "Execution"}
          </p>
          <h3 className="mt-1 text-[15px] font-semibold text-lab-text sm:text-base">
            72-hour gameplan
          </h3>
          <p className="mt-2 text-sm font-medium leading-snug text-lab-text sm:text-[15px]">
            Here&apos;s what you can do right now
          </p>
          <p className="mt-1.5 text-xs leading-relaxed text-lab-muted sm:text-sm">
            {isTracking
              ? "Certified mail is in flight — these moves keep pressure on outcomes during the investigation window. Skip anything you have already finished."
              : "Concrete moves tied to your file — not generic tips. Mail and track from this workflow; use scripts when a human picks up."}
          </p>
        </div>
        <span className="shrink-0 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-xs font-medium text-lab-muted">
          {open ? "Hide" : "Show"}
        </span>
      </button>

      <div className="mt-3 flex flex-wrap gap-2">
        <span className="rounded-full border border-white/[0.1] bg-white/[0.04] px-2.5 py-0.5 text-[11px] font-medium text-lab-text">
          {total_issues} issue{total_issues === 1 ? "" : "s"} in play
        </span>
        <span className="rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-200/90">
          {high_impact} high impact
        </span>
        <span className="rounded-full border border-red-400/20 bg-red-500/10 px-2.5 py-0.5 text-[11px] font-medium text-red-200/85">
          {score_damaging} score-damaging
        </span>
        <span className="rounded-full border border-emerald-400/20 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-200/85">
          {quick_wins} quick win{quick_wins === 1 ? "" : "s"}
        </span>
      </div>

      {open ? (
        <div className="mt-5 space-y-5 border-t border-white/[0.06] pt-5">
          {days.map((day, di) => (
            <div key={day.label}>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-lab-subtle">
                {day.label}
              </p>
              <ul className="mt-3 space-y-4">
                {day.actions.map((action) => (
                  <CommandPlanActionCard key={action.title} action={action} />
                ))}
              </ul>
              {di < days.length - 1 ? (
                <div className="mt-4 h-px bg-white/[0.04]" aria-hidden />
              ) : null}
            </div>
          ))}

          {isTracking ? <EscalationPathsCard /> : null}
        </div>
      ) : null}
    </motion.section>
  );
}
