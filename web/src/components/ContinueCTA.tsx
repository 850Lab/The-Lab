import { motion } from "framer-motion";

type Props = {
  onClick: () => void;
  label?: string;
  disabled?: boolean;
};

export function ContinueCTA({ onClick, label = "Continue", disabled = false }: Props) {
  return (
    <div className="w-full sm:flex sm:justify-center">
      <motion.button
        type="button"
        onClick={onClick}
        disabled={disabled}
        className="w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/20 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45 disabled:pointer-events-none disabled:opacity-50 sm:max-w-xs sm:px-10"
        whileHover={disabled ? undefined : { scale: 1.02, boxShadow: "0 12px 40px -10px rgba(59,130,246,0.4)" }}
        whileTap={disabled ? undefined : { scale: 0.98 }}
        transition={{ type: "spring", stiffness: 420, damping: 26 }}
      >
        {label}
      </motion.button>
    </div>
  );
}
