import { motion } from "framer-motion";

type Props = {
  onStart: () => void;
};

export function StrategyCTASection({ onStart }: Props) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-lab-elevated px-5 py-7 sm:px-8 sm:py-8">
      <h2 className="text-center text-lg font-semibold text-lab-text sm:text-xl">
        We’ll handle this for you
      </h2>
      <div className="mt-6 sm:flex sm:justify-center">
        <motion.button
          type="button"
          onClick={onStart}
          className="w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/25 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45 sm:max-w-sm sm:px-8"
          whileHover={{ scale: 1.02, boxShadow: "0 14px 44px -10px rgba(59,130,246,0.45)" }}
          whileTap={{ scale: 0.98 }}
          transition={{ type: "spring", stiffness: 400, damping: 26 }}
        >
          Start my disputes
        </motion.button>
      </div>
      <p className="mt-4 text-center text-xs text-lab-subtle sm:text-sm">
        Takes less than a minute to continue
      </p>
    </div>
  );
}
