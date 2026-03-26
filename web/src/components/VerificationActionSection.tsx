import { motion } from "framer-motion";

type Props = {
  canSend: boolean;
  onSend: () => void;
  onSaveLater: () => void;
};

export function VerificationActionSection({
  canSend,
  onSend,
  onSaveLater,
}: Props) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 14 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className="mt-10 space-y-3 sm:mt-11"
    >
      <motion.button
        type="button"
        disabled={!canSend}
        onClick={onSend}
        className="w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/25 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45 disabled:cursor-not-allowed disabled:bg-lab-accent/35 disabled:text-white/70 disabled:shadow-none"
        whileHover={
          canSend
            ? {
                scale: 1.015,
                boxShadow: "0 14px 44px -10px rgba(59,130,246,0.42)",
              }
            : undefined
        }
        whileTap={canSend ? { scale: 0.985 } : undefined}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
      >
        Send my disputes
      </motion.button>
      <p className="text-center text-xs text-lab-subtle sm:text-sm">
        You can save this and come back if needed
      </p>
      {!canSend ? (
        <p className="text-center text-sm text-lab-muted">
          Complete all three steps when you’re ready—we’ll hold your place.
        </p>
      ) : null}
      <motion.button
        type="button"
        onClick={onSaveLater}
        className="w-full rounded-xl border border-white/[0.12] bg-transparent py-3.5 text-[15px] font-medium text-lab-text transition-colors hover:border-white/[0.18] hover:bg-white/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35"
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.99 }}
        transition={{ type: "spring", stiffness: 480, damping: 30 }}
      >
        Save and finish later
      </motion.button>
    </motion.div>
  );
}
