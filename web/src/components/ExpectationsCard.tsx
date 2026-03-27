import { motion } from "framer-motion";

const LINES = [
  "Most bureaus respond within 30 days",
  "You may receive updates by mail",
  "We’ll guide you if more action is needed",
] as const;

type Props = {
  /** Optional backend hints (e.g. ``home_summary.nextBestAction``), shown first when present. */
  extraLines?: string[];
};

export function ExpectationsCard({ extraLines }: Props) {
  const extras = (extraLines ?? []).map((s) => s.trim()).filter(Boolean);
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
      className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 shadow-lg shadow-black/15 sm:px-6 sm:py-6"
    >
      <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
        What to expect
      </h3>
      <ul className="mt-4 space-y-3">
        {extras.map((line) => (
          <li
            key={line}
            className="flex gap-3 text-sm leading-relaxed text-lab-text/95"
          >
            <span
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-lab-accent"
              aria-hidden
            />
            {line}
          </li>
        ))}
        {LINES.map((line) => (
          <li
            key={line}
            className="flex gap-3 text-sm leading-relaxed text-lab-muted"
          >
            <span
              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-lab-accent/70"
              aria-hidden
            />
            {line}
          </li>
        ))}
      </ul>
    </motion.section>
  );
}
