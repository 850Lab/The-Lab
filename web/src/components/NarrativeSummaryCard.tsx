import {
  buildConfidenceMessage,
  buildOutcomeExpectation,
  buildPriorityInsights,
  buildSituationSummary,
  type NarrativeInput,
} from "@/lib/narrativeBuilder";

type Props = {
  input: NarrativeInput;
  className?: string;
  /** Slightly smaller type and air — e.g. strategy step where other cards sit below. */
  variant?: "default" | "compact";
};

/**
 * High-level narrative layer: situation, priorities, outcome, confidence.
 * Intentionally compact; does not replace step-specific copy elsewhere.
 */
export function NarrativeSummaryCard({ input, className = "", variant = "default" }: Props) {
  const situation = buildSituationSummary(input);
  const priorities = buildPriorityInsights(input);
  const outcome = buildOutcomeExpectation(input);
  const confidence = buildConfidenceMessage(input);

  const isCompact = variant === "compact";

  return (
    <section
      className={[
        "rounded-xl",
        isCompact
          ? "border border-white/[0.05] bg-white/[0.02] px-3.5 py-3.5 sm:px-4 sm:py-4"
          : "border border-white/[0.08] bg-gradient-to-b from-white/[0.04] to-lab-surface/80 px-4 py-4 sm:px-5 sm:py-5",
        className,
      ].join(" ")}
      aria-label="At a glance"
    >
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-subtle">At a glance</p>
      <p
        className={[
          "mt-2 leading-relaxed text-lab-text/95",
          isCompact ? "text-[13px] sm:text-sm" : "text-sm sm:text-[15px]",
        ].join(" ")}
      >
        {situation}
      </p>

      {priorities.length > 0 ? (
        <div className={`${isCompact ? "mt-3 border-white/[0.05] pt-3" : "mt-4 border-white/[0.06] pt-4"} border-t`}>
          <p className="text-xs font-semibold text-lab-text">Top priorities</p>
          <ul
            className={[
              "mt-2 list-none text-lab-muted",
              isCompact
                ? "space-y-2 text-[13px] leading-relaxed sm:text-sm"
                : "space-y-2.5 text-sm leading-relaxed sm:text-[15px]",
            ].join(" ")}
          >
            {priorities.map((line, i) => (
              <li
                key={i}
                className="relative pl-3.5 before:absolute before:left-0 before:top-2.5 before:h-1.5 before:w-1.5 before:rounded-full before:bg-lab-accent/60"
              >
                {line}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p
        className={[
          "text-lab-muted",
          isCompact ? "mt-3 text-[13px] leading-relaxed sm:text-sm" : "mt-4 text-sm leading-relaxed sm:text-[15px]",
        ].join(" ")}
      >
        {outcome}
      </p>
      <p
        className={[
          "text-lab-subtle",
          isCompact ? "mt-2.5 text-[11px] leading-relaxed sm:text-xs" : "mt-3 text-xs leading-relaxed sm:text-sm",
        ].join(" ")}
      >
        {confidence}
      </p>
    </section>
  );
}
