import { motion } from "framer-motion";

type Props = {
  onActivate: () => void;
};

export function PaymentCTASection({ onActivate }: Props) {
  return (
    <div className="pt-2">
      <motion.button
        type="button"
        onClick={onActivate}
        className="btn-primary-step w-full"
      >
        Start my disputes
      </motion.button>
      <p className="mt-3 text-center text-xs text-lab-subtle sm:text-sm">
        Secure payment. Takes less than a minute.
      </p>
    </div>
  );
}
