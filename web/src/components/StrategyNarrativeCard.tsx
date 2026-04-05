import { buildStrategyNarrative } from "@/lib/intelligenceExpression";
import type { DisputeStrategyPayload } from "@/lib/strategyTypes";

type Props = {
  strategy: DisputeStrategyPayload;
  themesText: string;
};

export function StrategyNarrativeCard({ strategy, themesText }: Props) {
  const sections = buildStrategyNarrative(strategy, themesText);
  return (
    <div className="rounded-xl border border-lab-accent/20 bg-lab-surface/80 px-5 py-5 sm:px-6 sm:py-6">
      <p className="text-xs font-semibold uppercase tracking-wide text-lab-accent">
        Your plan this round
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        Read this as a sequence — each block is why the program is pointing you here, not a dump of
        tasks.
      </p>
      <ol className="mt-5 space-y-5 border-t border-white/[0.06] pt-5">
        {sections.map((s, i) => (
          <li key={s.title}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-lab-subtle">
              {i + 1}. {s.title}
            </p>
            <p className="mt-2 text-[15px] leading-relaxed text-lab-text/95 sm:text-base">{s.body}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
