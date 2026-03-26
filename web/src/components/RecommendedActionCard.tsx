import { motion } from "framer-motion";
import type { EscalationOption } from "@/lib/escalationOptions";
import { DEFAULT_ESCALATION_ID } from "@/lib/escalationOptions";

type Props = {
  option: EscalationOption;
};

export function RecommendedActionCard({ option }: Props) {
  const isDefault = option.id === DEFAULT_ESCALATION_ID;

  return (
    <motion.section
      variants={{
        hidden: { opacity: 0, y: 16 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className="rounded-xl border border-lab-accent/25 bg-lab-elevated px-5 py-6 shadow-lg shadow-black/25 sm:px-6 sm:py-7"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-[15px] font-semibold text-lab-text sm:text-base">
          {isDefault ? "Recommended next step" : "Your next step"}
        </h2>
        {isDefault ? (
          <span className="rounded-full bg-lab-accent/15 px-2.5 py-0.5 text-xs font-medium text-lab-accent">
            Suggested
          </span>
        ) : (
          <span className="rounded-full bg-white/[0.08] px-2.5 py-0.5 text-xs font-medium text-lab-muted">
            Your choice
          </span>
        )}
      </div>

      <motion.div
        key={option.id}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
        className="mt-5"
      >
        <p className="text-lg font-semibold leading-snug tracking-tight text-lab-text sm:text-xl">
          {option.title}
        </p>
        <p className="mt-3 text-sm leading-relaxed text-lab-muted sm:text-[15px]">
          {option.support}
        </p>
        <p className="mt-4 border-t border-white/[0.08] pt-4 text-sm leading-relaxed text-lab-subtle">
          {option.reason}
        </p>
      </motion.div>
    </motion.section>
  );
}
