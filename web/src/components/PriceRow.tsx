type Props = {
  label: string;
  amountDisplay: string;
};

export function PriceRow({ label, amountDisplay }: Props) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-white/[0.08] pt-5">
      <span className="text-sm font-medium text-lab-muted">{label}</span>
      <span className="text-xl font-semibold tabular-nums tracking-tight text-lab-text sm:text-2xl">
        {amountDisplay}
      </span>
    </div>
  );
}
