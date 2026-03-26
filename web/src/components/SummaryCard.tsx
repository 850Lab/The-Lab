type Props = {
  totalCount: number;
};

export function SummaryCard({ totalCount }: Props) {
  return (
    <div className="rounded-xl border border-lab-accent/25 bg-lab-surface px-5 py-5 sm:px-6 sm:py-6">
      <p className="text-lg font-semibold leading-snug text-lab-text sm:text-xl">
        You have {totalCount} {totalCount === 1 ? "item" : "items"} we can help you challenge
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted sm:text-[15px]">
        We’ll guide you through fixing these step by step
      </p>
    </div>
  );
}
