import { motion } from "framer-motion";

const LINES = [
  "Mail tracking shows delivery progress — bureau outcomes are a separate timeline after they receive your package.",
  "It can take time for mail to move and for bureaus to work their review. You’re watching for meaningful updates, not daily changes.",
  "When a quiet period feels long, that can still be normal. Record a reply under Responses when mail arrives — we’ll point you to the next step.",
] as const;

type Props = {
  /** Optional backend hints (e.g. ``home_summary.nextBestAction``), shown first when present. */
  extraLines?: string[];
  heading?: string;
};

export function ExpectationsCard({ extraLines, heading = "What to expect next" }: Props) {
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
        {heading}
      </h3>
      <ul className="mt-4 space-y-3">
        {extras.map((line) => (
          <li
            key={line}
            className="flex gap-3 text-sm leading-relaxed text-lab-text/95"
          >
            <span className="lab-list-marker-lg" aria-hidden />
            {line}
          </li>
        ))}
        {LINES.map((line) => (
          <li
            key={line}
            className="flex gap-3 text-sm leading-relaxed text-lab-muted"
          >
            <span className="lab-list-marker-lg opacity-80" aria-hidden />
            {line}
          </li>
        ))}
      </ul>
    </motion.section>
  );
}
