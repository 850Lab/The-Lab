import { motion } from "framer-motion";

type Props = {
  onTrack: () => void;
};

export function MailingCTASection({ onTrack }: Props) {
  return (
    <div className="mt-10 sm:mt-11">
      <motion.button
        type="button"
        onClick={onTrack}
        className="w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/25 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45"
        whileHover={{
          scale: 1.015,
          boxShadow: "0 14px 44px -10px rgba(59,130,246,0.42)",
        }}
        whileTap={{ scale: 0.985 }}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
      >
        Track my disputes
      </motion.button>
    </div>
  );
}
