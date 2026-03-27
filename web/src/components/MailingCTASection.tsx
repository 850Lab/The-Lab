import { motion } from "framer-motion";

type Props = {
  onTrack: () => void;
  disabled?: boolean;
  busy?: boolean;
};

export function MailingCTASection({ onTrack, disabled, busy }: Props) {
  return (
    <div className="mt-10 sm:mt-11">
      <motion.button
        type="button"
        onClick={onTrack}
        disabled={disabled || busy}
        className="w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/25 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45 disabled:pointer-events-none disabled:bg-lab-accent/35 disabled:text-white/70 disabled:shadow-none"
        whileHover={
          disabled || busy
            ? undefined
            : {
                scale: 1.015,
                boxShadow: "0 14px 44px -10px rgba(59,130,246,0.42)",
              }
        }
        whileTap={disabled || busy ? undefined : { scale: 0.985 }}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
      >
        {busy ? "Loading…" : "Track my disputes"}
      </motion.button>
    </div>
  );
}
