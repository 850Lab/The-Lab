import { motion } from "framer-motion";

const DEFAULT_TRACK_BUTTON_CLASS =
  "w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-black/40 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45 disabled:pointer-events-none disabled:bg-lab-accent/35 disabled:text-white/70 disabled:shadow-none";

type Props = {
  onTrack: () => void;
  disabled?: boolean;
  busy?: boolean;
  headline?: string;
  supportText?: string;
  helperText?: string;
  trackLabel?: string;
  trackButtonClassName?: string;
};

export function MailingCTASection({
  onTrack,
  disabled,
  busy,
  headline = "Ready to move on to tracking?",
  supportText = "After mailing is confirmed for each bureau below, the next step is tracking your sends.",
  helperText = "Tracking begins after mailing is confirmed.",
  trackLabel = "Continue to tracking",
  trackButtonClassName,
}: Props) {
  return (
    <div className="mt-10 space-y-3 sm:mt-11">
      <div className="space-y-1 text-center">
        <p className="text-sm font-semibold text-lab-text">{headline}</p>
        <p className="text-sm leading-relaxed text-lab-muted">{supportText}</p>
      </div>
      <motion.button
        type="button"
        onClick={onTrack}
        disabled={disabled || busy}
        className={trackButtonClassName ?? DEFAULT_TRACK_BUTTON_CLASS}
        whileHover={
          disabled || busy
            ? undefined
            : {
                scale: 1.015,
                boxShadow: "0 14px 44px -10px rgba(0,0,0,0.55)",
              }
        }
        whileTap={disabled || busy ? undefined : { scale: 0.985 }}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
      >
        {busy ? "Loading…" : trackLabel}
      </motion.button>
      <p className="text-center text-xs text-lab-subtle">{helperText}</p>
    </div>
  );
}
