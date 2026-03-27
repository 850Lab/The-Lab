import { motion } from "framer-motion";

type Props = {
  onContinue: () => void;
  onDownloadBundle: () => void;
  continueDisabled: boolean;
  downloadDisabled: boolean;
  bundleBusy?: boolean;
};

export function LettersActionSection({
  onContinue,
  onDownloadBundle,
  continueDisabled,
  downloadDisabled,
  bundleBusy,
}: Props) {
  return (
    <div className="mt-10 space-y-3 sm:mt-11">
      <motion.button
        type="button"
        onClick={onContinue}
        disabled={continueDisabled}
        className="w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/25 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45 disabled:pointer-events-none disabled:opacity-45"
        whileHover={
          continueDisabled
            ? undefined
            : {
                scale: 1.015,
                boxShadow: "0 14px 44px -10px rgba(59,130,246,0.42)",
              }
        }
        whileTap={continueDisabled ? undefined : { scale: 0.985 }}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
      >
        We’ll send these for you
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
        {bundleBusy ? "Preparing download…" : "Download letters"}
      </motion.button>
    </div>
  );
}
