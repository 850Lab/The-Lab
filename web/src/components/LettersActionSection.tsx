import { motion } from "framer-motion";

type Props = {
  onContinue: () => void;
  onDownloadBundle: () => void;
  continueDisabled: boolean;
  downloadDisabled: boolean;
  bundleBusy?: boolean;
  continueLabel?: string;
  /** Framing above the primary action — trust and next-step clarity. */
  headline?: string;
  supportText?: string;
  /** Free vs paid clarity (e.g. download yourself vs we send). */
  freeValueLine?: string;
  /** Calm note under secondary action (e.g. mailing is later). */
  helperText?: string;
  /** ORION-driven visual emphasis on continue; default keeps `btn-primary-step`. */
  continueButtonClassName?: string;
};

export function LettersActionSection({
  onContinue,
  onDownloadBundle,
  continueDisabled,
  downloadDisabled,
  bundleBusy,
  continueLabel = "Continue to proof",
  headline = "Ready to continue preparing this round?",
  supportText = "Your letters are ready for review. The next step is to add proof documents and continue toward mailing.",
  freeValueLine,
  helperText = "Mailing happens later, after the next verification step.",
  continueButtonClassName,
}: Props) {
  return (
    <div className="mt-10 space-y-3 sm:mt-11">
      <div className="space-y-1 text-center">
        <p className="text-sm font-semibold text-lab-text">{headline}</p>
        <p className="text-sm leading-relaxed text-lab-muted">{supportText}</p>
        {freeValueLine ? (
          <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-lab-subtle/95 sm:text-sm">
            {freeValueLine}
          </p>
        ) : null}
      </div>
      <motion.button
        type="button"
        onClick={onContinue}
        disabled={continueDisabled}
        className={continueButtonClassName ?? "btn-primary-step w-full disabled:!opacity-[0.45]"}
      >
        {continueLabel}
      </motion.button>
      <motion.button
        type="button"
        onClick={onDownloadBundle}
        disabled={downloadDisabled || bundleBusy}
        className="w-full rounded-xl border border-white/[0.12] bg-transparent py-3.5 text-[15px] font-medium text-lab-text transition-colors hover:border-white/[0.18] hover:bg-white/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35 disabled:pointer-events-none disabled:opacity-45"
        whileHover={downloadDisabled || bundleBusy ? undefined : { y: -1 }}
        whileTap={downloadDisabled || bundleBusy ? undefined : { scale: 0.99 }}
        transition={{ type: "spring", stiffness: 480, damping: 30 }}
      >
        {bundleBusy ? "Preparing download…" : "Download all letters"}
      </motion.button>
      <p className="text-center text-xs text-lab-subtle">{helperText}</p>
    </div>
  );
}
