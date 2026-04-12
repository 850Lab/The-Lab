import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { transitionStepUi } from "@/lib/motionStep";

/**
 * Subtle entrance for the STEP main column — fade + 4px lift, ~220ms.
 * Parent page root must stay `relative`; ambient layers stay outside this wrapper.
 */
export function StepMainColumn({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <motion.main
      className={className}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transitionStepUi}
    >
      {children}
    </motion.main>
  );
}
