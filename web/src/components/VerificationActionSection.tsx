import { motion } from "framer-motion";

const DEFAULT_SEND_BUTTON_CLASS =
  "w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-black/40 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45 disabled:cursor-not-allowed disabled:bg-lab-accent/35 disabled:text-white/70 disabled:shadow-none";

type Props = {
  canSend: boolean;
  onSend: () => void;
  onSaveLater: () => void;
  sendBusy?: boolean;
  headline?: string;
  supportText?: string;
  helperText?: string;
  sendLabel?: string;
  incompleteMessage?: string;
  /** Override primary CTA styles (e.g. ORION-driven emphasis); default keeps existing accent button. */
  sendButtonClassName?: string;
};

export function VerificationActionSection({
  canSend,
  onSend,
  onSaveLater,
  sendBusy,
  headline = "Ready to complete this verification step?",
  supportText = "Once this step is complete, you’ll move to the final mailing screen where nothing is sent until you confirm there.",
  helperText = "Mailing is still reviewed on the next step.",
  sendLabel = "Continue to mailing",
  incompleteMessage = "Add the required items above to continue. If something is missing, we’ll let you know before you move on.",
  sendButtonClassName,
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
      <div className="space-y-1 text-center">
        <p className="text-sm font-semibold text-lab-text">{headline}</p>
        <p className="text-sm leading-relaxed text-lab-muted">{supportText}</p>
      </div>
      <motion.button
        type="button"
        disabled={!canSend || sendBusy}
        onClick={onSend}
        className={sendButtonClassName ?? DEFAULT_SEND_BUTTON_CLASS}
        whileHover={
          canSend && !sendBusy
            ? {
                scale: 1.015,
                boxShadow: "0 14px 44px -10px rgba(0,0,0,0.55)",
              }
            : undefined
        }
        whileTap={canSend && !sendBusy ? { scale: 0.985 } : undefined}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
      >
        {sendBusy ? "Continuing…" : sendLabel}
      </motion.button>
      <p className="text-center text-xs text-lab-subtle sm:text-sm">{helperText}</p>
      {!canSend ? (
        <p className="text-center text-sm text-lab-muted">{incompleteMessage}</p>
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
