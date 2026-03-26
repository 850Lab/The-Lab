import { motion } from "framer-motion";

type Props = {
  onContinue: () => void;
};

export function EscalationCTASection({ onContinue }: Props) {
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
        onClick={onContinue}
        className="w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/25 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45"
        whileHover={{
          scale: 1.015,
          boxShadow: "0 14px 44px -10px rgba(59,130,246,0.42)",
        }}
        whileTap={{ scale: 0.985 }}
        transition={{ type: "spring", stiffness: 420, damping: 28 }}
      >
        Continue with this step
      </motion.button>
      <p className="text-center text-xs text-lab-subtle sm:text-sm">
        We’ll prepare the next action for you
      </p>
    </motion.div>
  );
}
