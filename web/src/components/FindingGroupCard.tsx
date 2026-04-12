import { motion } from "framer-motion";
import { useState } from "react";

export type FindingGroupCardProps = {
  title: string;
  count: number;
  whyItMatters: string;
  whatWeSee: string;
  confidenceFraming: string;
  items: string[];
  /** First / highest-priority category in the sorted findings list. */
  featured?: boolean;
  /** Stable key from review_type (for analytics / keys only). */
  reviewType?: string;
  /** Short plain-language line under the title. */
  plainLanguageHint?: string;
  /** One-line guidance (tone: optional, in your control). */
  recommendationLine?: string;
  /** How many item bullets to show before "Show all". */
  initialVisibleItems?: number;
  /** Light surface for marketing-style / white pages (e.g. analysis results). */
  surface?: "dark" | "light";
};

const DEFAULT_VISIBLE = 3;

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
  plainLanguageHint,
  recommendationLine,
  initialVisibleItems = DEFAULT_VISIBLE,
  surface = "dark",
}: FindingGroupCardProps) {
  const [expanded, setExpanded] = useState(false);
  const light = surface === "light";
  const cap = Math.max(1, initialVisibleItems);
  const showToggle = items.length > cap;
  const visibleItems = expanded ? items : items.slice(0, cap);
  const hiddenCount = items.length - cap;

  return (
    <motion.article
      layout
      className={`rounded-xl border px-5 py-5 sm:px-6 sm:py-6 ${
        light
          ? featured
            ? "border-neutral-300/90 bg-gradient-to-b from-neutral-50 to-white shadow-sm shadow-neutral-900/5"
            : "border-neutral-200/90 bg-white shadow-sm shadow-neutral-900/[0.04]"
          : featured
            ? "border-zinc-600/45 bg-lab-surface shadow-md shadow-black/25"
            : "border-white/[0.06] bg-lab-surface"
      }`}
      variants={cardVariants}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3
              className={`text-base font-semibold sm:text-lg ${light ? "text-neutral-950" : "text-lab-text"}`}
            >
              {title}
            </h3>
            {featured ? (
              <span
                className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                  light
                    ? "border border-neutral-400/40 bg-neutral-100 text-neutral-600"
                    : "bg-lab-accent/15 text-zinc-300/95"
                }`}
              >
                Suggested first pass
              </span>
            ) : null}
          </div>
          {recommendationLine ? (
            <p
              className={`mt-2 text-xs font-medium leading-snug ${
                light ? "text-neutral-600" : "text-zinc-300/85"
              }`}
            >
              {recommendationLine}
            </p>
          ) : null}
          {plainLanguageHint ? (
            <p
              className={`mt-2 max-w-prose text-sm leading-relaxed ${
                light ? "text-neutral-600" : "text-lab-muted"
              }`}
            >
              {plainLanguageHint}
            </p>
          ) : null}
        </div>
        <span
          className={`shrink-0 text-sm font-medium tabular-nums ${
            light ? "text-neutral-500" : "text-lab-accent"
          }`}
        >
          {count}
        </span>
      </div>
      <dl className="mt-4 space-y-3 text-sm leading-relaxed">
        <div>
          <dt
            className={`text-[11px] font-semibold uppercase tracking-[0.12em] ${
              light ? "text-neutral-500" : "text-lab-subtle"
            }`}
          >
            Why this matters
          </dt>
          <dd
            className={`mt-1 max-w-prose ${light ? "text-neutral-800" : "text-lab-text/95"}`}
          >
            {whyItMatters}
          </dd>
        </div>
        <div>
          <dt
            className={`text-[11px] font-semibold uppercase tracking-wide ${
              light ? "text-neutral-500" : "text-lab-accent/90"
            }`}
          >
            What we see
          </dt>
          <dd className={`mt-1 max-w-prose ${light ? "text-neutral-600" : "text-lab-muted"}`}>
            {whatWeSee}
          </dd>
        </div>
        <div>
          <dt
            className={`text-[11px] font-semibold uppercase tracking-wide ${
              light ? "text-neutral-500" : "text-lab-subtle"
            }`}
          >
            How strong is this bucket?
          </dt>
          <dd className={`mt-1 max-w-prose ${light ? "text-neutral-600" : "text-lab-muted"}`}>
            {confidenceFraming}
          </dd>
        </div>
      </dl>
      <ul
        className={`mt-4 space-y-2.5 border-t pt-4 ${
          light ? "border-neutral-200" : "border-white/[0.06]"
        }`}
      >
        {visibleItems.map((label) => (
          <li
            key={label}
            className={`flex gap-2.5 text-sm ${light ? "text-neutral-800" : "text-lab-text/90"}`}
          >
            <span
              className={`mt-2 h-1 w-1 shrink-0 rounded-full ${light ? "bg-neutral-400" : "lab-list-marker"}`}
              aria-hidden
            />
            <span className="max-w-prose leading-relaxed">{label}</span>
          </li>
        ))}
      </ul>
      {showToggle ? (
        <div className={`mt-3 border-t pt-3 ${light ? "border-neutral-200" : "border-white/[0.04]"}`}>
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className={`text-sm font-medium ${
              light
                ? "text-neutral-800 underline-offset-2 hover:underline"
                : "text-lab-accent hover:text-lab-accent/90"
            }`}
          >
            {expanded ? "Show fewer" : `Show all ${items.length} items`}
            {!expanded && hiddenCount > 0 ? (
              <span className="text-lab-muted"> ({hiddenCount} more grouped for review)</span>
            ) : null}
          </button>
        </div>
      ) : null}
    </motion.article>
  );
}
