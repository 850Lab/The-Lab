export type DisputeItemRowProps = {
  company: string;
  issueLabel: string;
  onRemove: () => void;
};

export function DisputeItemRow({ company, issueLabel, onRemove }: DisputeItemRowProps) {
  return (
    <div className="flex items-start justify-between gap-3 py-3.5 sm:py-4">
      <div className="min-w-0 flex-1 text-left">
        <p className="text-[15px] font-medium text-lab-text">{company}</p>
        <p className="mt-0.5 text-sm leading-relaxed text-lab-muted">{issueLabel}</p>
      </div>
      <button
        type="button"
        onClick={onRemove}
        className="shrink-0 rounded-lg px-2 py-1.5 text-xs font-medium text-lab-subtle transition-colors hover:bg-white/[0.05] hover:text-lab-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/40"
      >
        Remove
      </button>
    </div>
  );
}
