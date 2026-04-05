import { motion } from "framer-motion";

export type FindingGroupCardProps = {
  title: string;
  count: number;
  whyItMatters: string;
  whatWeSee: string;
  confidenceFraming: string;
  items: string[];
  /** First / highest-priority category in the sorted findings list. */
  featured?: boolean;
};

const cardVariants = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

export function FindingGroupCard({
  title,
  count,
  whyItMatters,
  whatWeSee,
  confidenceFraming,
  items,
  featured,
}: FindingGroupCardProps) {
  return (
    <motion.article
      layout
      className={`rounded-xl border bg-lab-surface px-5 py-5 sm:px-6 sm:py-6 ${
        featured
          ? "border-lab-accent/35 shadow-md shadow-lab-accent/[0.07]"
          : "border-white/[0.06]"
      }`}
      variants={cardVariants}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-lab-text sm:text-lg">{title}</h3>
          {featured ? (
            <span className="rounded-md bg-lab-accent/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-200/95">
              Worth a closer look first
            </span>
          ) : null}
        </div>
        <span className="text-sm font-medium tabular-nums text-lab-accent">{count}</span>
      </div>
      <dl className="mt-3 space-y-3 text-sm leading-relaxed">
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-lab-accent/90">
            Why this matters
          </dt>
          <dd className="mt-1 text-lab-text/95">{whyItMatters}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-lab-accent/90">
            What we see
          </dt>
          <dd className="mt-1 text-lab-muted">{whatWeSee}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-semibold uppercase tracking-wide text-lab-subtle">
            How strong is this bucket?
          </dt>
          <dd className="mt-1 text-lab-muted">{confidenceFraming}</dd>
        </div>
      </dl>
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
