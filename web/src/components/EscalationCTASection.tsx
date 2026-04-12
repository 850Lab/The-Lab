import { motion } from "framer-motion";
import type { ReactNode } from "react";

type Props = {
  onContinue: () => void;
  footerHint?: string;
  headline?: string;
  supportingText?: string;
  primaryLabel?: string;
  afterButton?: ReactNode;
};

export function EscalationCTASection({
  onContinue,
  footerHint,
  headline = "Ready to review a next-step action?",
  supportingText = "Choose the option that best fits what has happened in this round so far. You can still return to Tracking or Responses before acting.",
  primaryLabel = "Continue to next-step checklist",
  afterButton,
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
      className="mt-10 space-y-4 sm:mt-11"
    >
      <div className="text-center">
        <p className="text-sm font-semibold text-lab-text">{headline}</p>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-lab-muted">
          {supportingText}
        </p>
      </div>
      <motion.button
        type="button"
        onClick={onContinue}
        className="btn-primary-step w-full"
      >
        {primaryLabel}
      </motion.button>
      <p className="text-center text-xs text-lab-subtle sm:text-sm">
        {footerHint ?? "Opens a focused checklist for the path you selected."}
      </p>
      {afterButton}
    </motion.div>
  );
}
