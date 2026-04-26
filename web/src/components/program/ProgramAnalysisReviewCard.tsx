import type { ProgramAnalysisFindingModel } from "@/lib/programAnalysisFindings";
import { PROGRAM_ANALYSIS_TIER_LABEL } from "@/lib/programAnalysisFindings";

type Props = {
  finding: ProgramAnalysisFindingModel;
  index: number;
  total: number;
  onBack: () => void;
  onNext: () => void;
  /** Guided CTA arm from `useOrionProgramAdvancement` for ANALYSIS_REVIEW */
  nextCtaArmReady: boolean;
  /** Operational counts line (prepared / held) */
  operationalSummary?: string;
};

export function ProgramAnalysisReviewCard({
  finding,
  index,
  total,
  onBack,
  onNext,
  nextCtaArmReady,
  operationalSummary,
}: Props) {
  const tierLabel = PROGRAM_ANALYSIS_TIER_LABEL[finding.tier];
  return (
    <article
      key={finding.id}
      className="rounded-xl border border-white/[0.1] bg-lab-surface px-4 py-5 transition-opacity duration-200 sm:px-6"
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-lab-subtle">
        Prepared issue {index + 1} of {total} · {tierLabel}
      </p>
      <h2 className="mt-2 text-lg font-semibold leading-snug text-lab-text">{finding.title}</h2>
      <p className="mt-3 text-sm leading-relaxed text-lab-muted">{finding.summary}</p>
      {operationalSummary ? (
        <p className="mt-2 text-xs font-medium text-slate-400">{operationalSummary}</p>
      ) : null}
      <div className="mt-5 space-y-2 rounded-lg border border-white/[0.06] bg-lab-elevated/50 px-3 py-3">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-lab-subtle">Why it matters</p>
        <p className="text-sm leading-relaxed text-lab-text/95">{finding.whyItMatters}</p>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <span className="rounded-full border border-slate-500/35 bg-slate-500/10 px-3 py-1 text-xs font-medium text-slate-200">
          {finding.orionStatus}
        </span>
      </div>
      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
        <button
          type="button"
          onClick={onBack}
          disabled={index <= 0}
          className="rounded-md border border-white/15 px-4 py-2 text-sm font-medium text-lab-text hover:bg-white/5 disabled:pointer-events-none disabled:opacity-35"
        >
          Back
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={!nextCtaArmReady}
          className="rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 transition-opacity duration-200 hover:brightness-110 disabled:pointer-events-none disabled:opacity-35"
        >
          {index >= total - 1 ? "Finish Case Review" : "Next prepared issue"}
        </button>
      </div>
    </article>
  );
}
