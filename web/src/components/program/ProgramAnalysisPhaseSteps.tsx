import type { ProgramAnalysisPhase } from "@/lib/programAnalysisPhase";
import { PROGRAM_ANALYSIS_PHASES } from "@/lib/programAnalysisPhase";
import { PROGRAM_ANALYSIS_STEP_LABELS } from "@/lib/orionProgramAnalysisCopy";

type Props = {
  active: ProgramAnalysisPhase;
  /** When there are no findings, hide middle steps in the rail. */
  compact?: boolean;
};

export function ProgramAnalysisPhaseSteps({ active, compact }: Props) {
  const phases = compact
    ? (["ANALYSIS_INTRO", "STRATEGY_HANDOFF"] as ProgramAnalysisPhase[])
    : [...PROGRAM_ANALYSIS_PHASES];
  const resolvedActive = phases.includes(active) ? active : phases[phases.length - 1]!;
  const activeIndex = phases.indexOf(resolvedActive);
  return (
    <ol className="flex flex-wrap items-center gap-2" aria-label="Analysis progress">
      {phases.map((p, i) => {
        const done = activeIndex > i;
        const current = p === resolvedActive;
        return (
          <li key={p} className="flex items-center gap-2">
            {i > 0 ? (
              <span className="text-lab-subtle select-none" aria-hidden>
                →
              </span>
            ) : null}
            <span
              className={[
                "rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide",
                current
                  ? "bg-lab-accent/25 text-lab-text ring-1 ring-lab-accent/40"
                  : done
                    ? "bg-white/[0.06] text-lab-muted"
                    : "bg-transparent text-lab-subtle",
              ].join(" ")}
              aria-current={current ? "step" : undefined}
            >
              {PROGRAM_ANALYSIS_STEP_LABELS[p]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
