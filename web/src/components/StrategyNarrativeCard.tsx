import { buildStrategyNarrative } from "@/lib/intelligenceExpression";
import type { DisputeStrategyPayload } from "@/lib/strategyTypes";

type Props = {
  strategy: DisputeStrategyPayload;
  themesText: string;
};

export function StrategyNarrativeCard({ strategy, themesText }: Props) {
  const sections = buildStrategyNarrative(strategy, themesText);
  const head = sections.slice(0, 2);
  const tail = sections.slice(2);

  return (
    <div className="rounded-xl border border-lab-accent/20 bg-lab-surface/80 px-5 py-5 sm:px-6 sm:py-6">
      <p className="text-xs font-semibold uppercase tracking-wide text-lab-accent">
        How this round fits together
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        Short reads — you&apos;re confirming direction, not doing legal homework. Focused rounds are
        often stronger than trying to challenge everything at once.
      </p>
      <ol className="mt-5 space-y-5 border-t border-white/[0.06] pt-5">
        {head.map((s, i) => (
          <li key={s.title}>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-lab-subtle">
              {i + 1}. {s.title}
            </p>
            <p className="mt-2 text-[15px] leading-relaxed text-lab-text/95 sm:text-base">{s.body}</p>
          </li>
        ))}
      </ol>

      {tail.length > 0 ? (
        <details className="mt-5 rounded-lg border border-white/[0.08] bg-black/[0.12] px-4 py-3 sm:px-5 sm:py-4">
          <summary className="cursor-pointer text-sm font-semibold text-lab-text hover:text-lab-accent/90">
            More context (optional)
          </summary>
          <ol className="mt-4 space-y-5 border-t border-white/[0.06] pt-4">
            {tail.map((s, i) => (
              <li key={s.title}>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-lab-subtle">
                  {head.length + i + 1}. {s.title}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted sm:text-[15px]">{s.body}</p>
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </div>
  );
}
