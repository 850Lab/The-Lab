type Props = {
  selected: boolean;
  disabled?: boolean;
  onClick: () => void;
};

/**
 * Tertiary entry to “Something else happened” — same visual weight as step cards, not an alert.
 */
export function OtherOutcomeTrigger({ selected, disabled, onClick }: Props) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={[
        "flex w-full items-center justify-center gap-2 rounded-xl border px-4 py-3.5 text-left text-sm transition-colors",
        "min-h-[44px] sm:py-3",
        selected
          ? "border-zinc-500/45 bg-zinc-500/[0.12] font-medium text-lab-text ring-1 ring-zinc-500/25"
          : "border-white/[0.1] bg-black/20 text-lab-muted hover:border-white/[0.14] hover:bg-black/30 hover:text-lab-text",
        disabled ? "pointer-events-none opacity-45" : "",
      ].join(" ")}
    >
      <span>Something else happened</span>
      <span className="text-lab-subtle" aria-hidden>
        →
      </span>
    </button>
  );
}
