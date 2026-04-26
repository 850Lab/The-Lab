import type { ProgramAnalysisConfirmationStance } from "@/lib/programAnalysisPhase";
import type { ProgramAnalysisFindingModel } from "@/lib/programAnalysisFindings";

type Props = {
  findings: ProgramAnalysisFindingModel[];
  stancesByClaimId: Record<string, ProgramAnalysisConfirmationStance>;
  onSetStance: (claimId: string, stance: ProgramAnalysisConfirmationStance) => void;
  onBack: () => void;
  onContinue: () => void;
  continueDisabled: boolean;
  continueCtaLabel: string;
  blockedMessage?: string;
  /** Soft reveal for blocked/guided timing (opacity only). */
  ctaRevealSoft?: boolean;
};

const STANCE_OPTIONS: { stance: ProgramAnalysisConfirmationStance; label: string }[] = [
  { stance: "confirm_for_strategy", label: "Confirm for strategy" },
  { stance: "remove_from_review", label: "Remove from review" },
  { stance: "mark_closer_look", label: "Mark for closer look" },
];

export function ProgramAnalysisConfirmationPanel({
  findings,
  stancesByClaimId,
  onSetStance,
  onBack,
  onContinue,
  continueDisabled,
  continueCtaLabel,
  blockedMessage,
  ctaRevealSoft = true,
}: Props) {
  return (
    <div className="space-y-5">
      <ul className="space-y-4">
        {findings.map((f) => {
          const stance = stancesByClaimId[f.id] ?? "confirm_for_strategy";
          return (
            <li
              key={f.id}
              className="rounded-xl border border-white/[0.08] bg-lab-surface/90 px-4 py-4 sm:px-5"
            >
              <p className="text-sm font-semibold text-lab-text">{f.title}</p>
              <p className="mt-1 text-xs leading-relaxed text-lab-muted line-clamp-2">{f.summary}</p>
              <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                {STANCE_OPTIONS.map(({ stance: s, label }) => {
                  const on = stance === s;
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => onSetStance(f.id, s)}
                      className={[
                        "rounded-md px-3 py-2 text-left text-xs font-semibold sm:text-sm",
                        on
                          ? "bg-lab-accent text-zinc-950 ring-1 ring-lab-accent"
                          : "border border-white/12 bg-lab-elevated/40 text-lab-muted hover:border-white/20 hover:text-lab-text",
                      ].join(" ")}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ul>
      <div
        className={[
          "flex flex-col-reverse gap-3 transition-opacity duration-200 sm:flex-row sm:justify-between",
          ctaRevealSoft ? "opacity-100" : "opacity-35",
        ].join(" ")}
      >
        <button
          type="button"
          onClick={onBack}
          className="rounded-md border border-white/15 px-4 py-2 text-sm font-medium text-lab-text hover:bg-white/5"
        >
          Back to walkthrough
        </button>
        <button
          type="button"
          onClick={onContinue}
          disabled={continueDisabled}
          className="rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 hover:brightness-110 disabled:pointer-events-none disabled:opacity-40"
        >
          {continueCtaLabel}
        </button>
      </div>
      {continueDisabled && blockedMessage ? (
        <p className="text-sm leading-relaxed text-amber-100/90">{blockedMessage}</p>
      ) : null}
    </div>
  );
}
