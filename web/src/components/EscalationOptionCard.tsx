import { motion } from "framer-motion";
import type { EscalationOption } from "@/lib/escalationOptions";

type Props = {
  option: EscalationOption;
  selected: boolean;
  onSelect: () => void;
};

export function EscalationOptionCard({
  option,
  selected,
  onSelect,
}: Props) {
  return (
    <motion.button
      type="button"
      onClick={onSelect}
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className={`w-full rounded-xl border px-4 py-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35 sm:px-5 sm:py-4 ${
        selected
          ? "border-lab-accent/45 bg-lab-accent/[0.08] shadow-md shadow-lab-accent/10"
          : "border-white/[0.08] bg-lab-surface hover:border-white/[0.14] hover:bg-lab-elevated/60"
      }`}
      whileTap={{ scale: 0.992 }}
      transition={{ type: "spring", stiffness: 520, damping: 32 }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
              {option.title}
            </h3>
            {option.recommended ? (
              <span className="shrink-0 rounded-full bg-lab-accent/12 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-lab-accent">
                Recommended
              </span>
            ) : null}
          </div>
          <p className="mt-2 text-sm leading-relaxed text-lab-muted">
            {option.support}
          </p>
        </div>
        <span
          className={`mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors ${
            selected
              ? "border-lab-accent bg-lab-accent"
              : "border-white/[0.2] bg-transparent"
          }`}
          aria-hidden
        >
          {selected ? (
            <svg
              className="h-2.5 w-2.5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={3}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
          ) : null}
        </span>
      </div>
      {selected ? (
        <motion.p
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          className="mt-3 text-xs font-medium text-lab-accent"
        >
          Selected — we’ll use this for your next action
        </motion.p>
      ) : null}
    </motion.button>
  );
}
