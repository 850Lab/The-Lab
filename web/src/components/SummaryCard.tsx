type Props = {
  totalCount: number;
  /** When set, replaces the default secondary line (e.g. findings vs review step). */
  subline?: string;
};

export function SummaryCard({ totalCount, subline }: Props) {
  return (
    <div className="rounded-xl border border-lab-accent/25 bg-lab-surface px-5 py-5 sm:px-6 sm:py-6">
      <p className="text-lg font-semibold leading-snug text-lab-text sm:text-xl">
        We found {totalCount} meaningful {totalCount === 1 ? "issue" : "issues"} to look at
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted sm:text-[15px]">
        {subline ??
          "They’re grouped below so you can see what kind of problems showed up — not a raw dump of every line on your report."}
      </p>
    </div>
  );
}
