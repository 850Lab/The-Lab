import { OTHER_OUTCOME_TEXT_MAX } from "@/lib/executionOutcomeTypes";

type Props = {
  otherText: string;
  notSure: boolean;
  onOtherTextChange: (value: string) => void;
  onNotSureChange: (value: boolean) => void;
  onUseStandard: () => void;
  onSubmit: () => void;
  canSubmit: boolean;
  submitting?: boolean;
};

export function OtherOutcomePanel({
  otherText,
  notSure,
  onOtherTextChange,
  onNotSureChange,
  onUseStandard,
  onSubmit,
  canSubmit,
  submitting,
}: Props) {
  return (
    <div className="mt-5 rounded-2xl border border-white/[0.1] bg-lab-surface/50 p-4 sm:p-5">
      <p className="text-sm font-medium leading-snug text-lab-text">
        That&apos;s okay — plans hit real-world twists.
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        In a sentence or two, what happened?
      </p>

      <label htmlFor="execution-other-outcome" className="sr-only">
        What happened
      </label>
      <input
        id="execution-other-outcome"
        type="text"
        maxLength={OTHER_OUTCOME_TEXT_MAX}
        value={otherText}
        onChange={(e) => onOtherTextChange(e.target.value)}
        disabled={!!submitting}
        placeholder="e.g. They sent a letter, but it wasn't for my account"
        className="mt-4 w-full rounded-xl border border-white/[0.12] bg-black/30 px-3.5 py-3 text-sm text-lab-text placeholder:text-lab-subtle/80 focus:border-lab-accent/40 focus:outline-none focus:ring-1 focus:ring-lab-accent/30 disabled:opacity-50"
        autoComplete="off"
      />
      <p className="mt-1.5 text-right text-[11px] text-lab-subtle">
        {otherText.length}/{OTHER_OUTCOME_TEXT_MAX}
      </p>

      <label className="mt-4 flex cursor-pointer items-start gap-3 text-sm text-lab-muted">
        <input
          type="checkbox"
          checked={notSure}
          disabled={!!submitting}
          onChange={(e) => onNotSureChange(e.target.checked)}
          className="mt-0.5 h-4 w-4 shrink-0 rounded border-white/20 bg-black/40 text-lab-accent focus:ring-lab-accent/40"
        />
        <span>I&apos;m not sure how to describe it</span>
      </label>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row-reverse sm:items-center sm:justify-end">
        <button
          type="button"
          disabled={!canSubmit || submitting}
          onClick={onSubmit}
          className="min-h-[44px] rounded-xl bg-lab-accent px-5 py-3 text-center text-sm font-semibold text-lab-bg transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? "Saving…" : "Save & continue"}
        </button>
        <button
          type="button"
          disabled={!!submitting}
          onClick={onUseStandard}
          className="min-h-[44px] rounded-xl border border-white/[0.12] bg-transparent px-4 py-3 text-center text-sm text-lab-muted transition-colors hover:border-white/[0.18] hover:text-lab-text disabled:opacity-40"
        >
          Use a standard option instead
        </button>
      </div>
    </div>
  );
}
