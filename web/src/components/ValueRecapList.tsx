type Props = {
  lines: string[];
};

export function ValueRecapList({ lines }: Props) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-lab-text">What happens next</h3>
      <ul className="mt-3 space-y-2.5">
        {lines.map((line) => (
          <li key={line} className="flex gap-2.5 text-sm leading-relaxed text-lab-muted">
            <span
              className="mt-2 h-1 w-1 shrink-0 rounded-full bg-lab-accent/55"
              aria-hidden
            />
            <span>{line}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
