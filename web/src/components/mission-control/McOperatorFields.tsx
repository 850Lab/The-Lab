type Props = {
  actorSource: string;
  reasonSafe: string;
  onActorSource: (v: string) => void;
  onReasonSafe: (v: string) => void;
  disabled?: boolean;
};

export function McOperatorFields({
  actorSource,
  reasonSafe,
  onActorSource,
  onReasonSafe,
  disabled,
}: Props) {
  return (
    <div className="space-y-3 text-sm">
      <label className="block">
        <span className="text-lab-muted text-xs">actor_source</span>
        <input
          className="mt-1 w-full rounded border border-white/15 bg-lab-elevated px-2 py-1.5 font-mono text-xs text-lab-text"
          value={actorSource}
          onChange={(e) => onActorSource(e.target.value)}
          disabled={disabled}
          autoComplete="off"
        />
      </label>
      <label className="block">
        <span className="text-lab-muted text-xs">reason_safe</span>
        <textarea
          className="mt-1 w-full min-h-[72px] rounded border border-white/15 bg-lab-elevated px-2 py-1.5 text-xs text-lab-text"
          value={reasonSafe}
          onChange={(e) => onReasonSafe(e.target.value)}
          disabled={disabled}
        />
      </label>
    </div>
  );
}
