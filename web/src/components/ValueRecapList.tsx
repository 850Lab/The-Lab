type Props = {
  lines: string[];
  /** Section heading; default matches legacy payment copy. */
  title?: string;
};

export function ValueRecapList({ lines, title = "What this unlocks" }: Props) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-lab-text">{title}</h3>
      <ul className="mt-3 space-y-2.5">
        {lines.map((line) => (
          <li key={line} className="flex gap-2.5 text-sm leading-relaxed text-lab-muted">
            <span className="lab-list-marker" aria-hidden />
            <span>{line}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
