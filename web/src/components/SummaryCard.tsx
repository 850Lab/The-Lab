type Props = {
  totalCount: number;
  /** When set, replaces the default secondary line (e.g. findings vs review step). */
  subline?: string;
};

export function SummaryCard({ totalCount, subline }: Props) {
  return (
    <div className="rounded-xl border border-zinc-800/70 bg-lab-surface px-5 py-5 sm:px-6 sm:py-6">
      <p className="text-lg font-semibold leading-snug text-lab-text sm:text-xl">
        {totalCount} {totalCount === 1 ? "item was" : "items were"} organized for review
      </p>
      <p className="mt-2 max-w-prose text-sm leading-relaxed text-lab-muted sm:text-[15px]">
        {subline ??
          "They’re grouped below so you can review faster — not to suggest everything should be disputed in one round."}
      </p>
    </div>
  );
}
