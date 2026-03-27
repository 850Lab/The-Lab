export type PreparedCategory = {
  label: string;
  count: number;
};

type Props = {
  categories: PreparedCategory[];
};

export function PreparedItemsSummary({ categories }: Props) {
  return (
    <div className="rounded-lg border border-white/[0.06] bg-lab-bg/40 px-4 py-3.5">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-lab-subtle">
        What you’re paying for (this round)
      </p>
      <dl className="mt-3 space-y-2">
        {categories.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between gap-4 text-sm"
          >
            <dt className="text-lab-muted">{row.label}</dt>
            <dd className="tabular-nums font-medium text-lab-text">{row.count}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
