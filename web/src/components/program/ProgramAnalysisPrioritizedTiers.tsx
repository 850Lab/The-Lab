import type { ProgramAnalysisFindingModel } from "@/lib/programAnalysisFindings";
import {
  PROGRAM_ANALYSIS_TIER_LABEL,
  PROGRAM_ANALYSIS_TIER_ORDER,
  type ProgramAnalysisTierKey,
} from "@/lib/programAnalysisFindings";

type Props = {
  byTier: Record<ProgramAnalysisTierKey, ProgramAnalysisFindingModel[]>;
  onContinue: () => void;
  ctaLabel: string;
  /** From `useOrionProgramAdvancement` — guided reveal + gate. */
  ctaArmReady: boolean;
};

export function ProgramAnalysisPrioritizedTiers({ byTier, onContinue, ctaLabel, ctaArmReady }: Props) {
  return (
    <div className="space-y-6">
      <p className="text-xs text-lab-muted">
        Prepared issues are grouped by how strongly they should shape your correction path — not a final
        dispute list until you carry them forward.
      </p>
      <div className="space-y-5">
        {PROGRAM_ANALYSIS_TIER_ORDER.map((tier) => {
          const list = byTier[tier];
          if (!list.length) return null;
          return (
            <div key={tier} className="rounded-xl border border-white/[0.08] bg-lab-surface/80 px-4 py-4">
              <div className="flex items-baseline justify-between gap-2">
                <h2 className="text-sm font-semibold text-lab-text">{PROGRAM_ANALYSIS_TIER_LABEL[tier]}</h2>
                <span className="text-xs tabular-nums text-lab-subtle">{list.length}</span>
              </div>
              <ul className="mt-3 space-y-2">
                {list.map((f) => (
                  <li
                    key={f.id}
                    className="rounded-lg border border-white/[0.05] bg-lab-elevated/40 px-3 py-2.5 text-sm text-lab-text"
                  >
                    <p className="font-medium leading-snug">{f.title}</p>
                    <p className="mt-1 text-xs leading-relaxed text-lab-muted line-clamp-2">{f.summary}</p>
                    <p className="mt-2 text-[11px] font-medium uppercase tracking-wide text-cyan-200/85">
                      {f.orionStatus}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
      <div className="flex justify-end">
        <button
          type="button"
          onClick={onContinue}
          disabled={!ctaArmReady}
          className="rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 transition-opacity duration-200 hover:brightness-110 disabled:pointer-events-none disabled:opacity-35"
        >
          {ctaLabel}
        </button>
      </div>
    </div>
  );
}
