import { motion } from "framer-motion";

export type FindingGroupCardProps = {
  title: string;
  count: number;
  explanation: string;
  items: string[];
};

const cardVariants = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

export function FindingGroupCard({ title, count, explanation, items }: FindingGroupCardProps) {
  return (
    <motion.article
      layout
      className="rounded-xl border border-white/[0.06] bg-lab-surface px-5 py-5 sm:px-6 sm:py-6"
      variants={cardVariants}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-base font-semibold text-lab-text sm:text-lg">{title}</h3>
        <span className="text-sm font-medium tabular-nums text-lab-accent">{count}</span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">{explanation}</p>
      <ul className="mt-4 space-y-2.5 border-t border-white/[0.06] pt-4">
        {items.map((label) => (
          <li key={label} className="flex gap-2.5 text-sm text-lab-text/90">
            <span
              className="mt-2 h-1 w-1 shrink-0 rounded-full bg-lab-accent/70"
              aria-hidden
            />
            <span className="leading-relaxed">{label}</span>
          </li>
        ))}
      </ul>
    </motion.article>
  );
}
