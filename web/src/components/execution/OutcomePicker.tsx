import { OtherOutcomeTrigger } from "@/components/execution/OtherOutcomeTrigger";

export type PredefinedOutcomeOption = { id: string; label: string };

type Props = {
  options: PredefinedOutcomeOption[];
  selectedPredefinedId: string | null;
  otherSelected: boolean;
  onSelectPredefined: (id: string) => void;
  onSelectOther: () => void;
  disabled?: boolean;
};

export function OutcomePicker({
  options,
  selectedPredefinedId,
  otherSelected,
  onSelectPredefined,
  onSelectOther,
  disabled,
}: Props) {
  return (
    <div className="space-y-3">
      <p className="step-eyebrow-left text-left">What happened?</p>

      <ul className="space-y-2.5">
        {options.map((opt) => {
          const selected = !otherSelected && selectedPredefinedId === opt.id;
          return (
            <li key={opt.id}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onSelectPredefined(opt.id)}
                className={[
                  "flex w-full min-h-[44px] items-center rounded-xl border px-4 py-3.5 text-left text-sm transition-colors sm:py-3",
                  selected
                    ? "border-zinc-500/45 bg-zinc-500/[0.12] font-medium text-lab-text ring-1 ring-zinc-500/25"
                    : "border-white/[0.1] bg-black/20 text-lab-muted hover:border-white/[0.14] hover:bg-black/30 hover:text-lab-text",
                  disabled ? "pointer-events-none opacity-45" : "",
                ].join(" ")}
              >
                {opt.label}
              </button>
            </li>
          );
        })}
      </ul>

      <div className="pt-2">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-[0.14em] text-lab-subtle">More options</p>
        <OtherOutcomeTrigger
          selected={otherSelected}
          disabled={disabled}
          onClick={onSelectOther}
        />
      </div>
    </div>
  );
}
