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
        className="btn-primary-step w-full sm:max-w-xs sm:px-10"
      >
        {label}
      </motion.button>
    </div>
  );
}
