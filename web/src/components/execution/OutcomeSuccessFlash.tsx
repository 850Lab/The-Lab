type Props = {
  visible: boolean;
  /** Defaults to guided-execution copy */
  message?: string;
};

export function OutcomeSuccessFlash({
  visible,
  message = "Got it — we'll adjust your next step.",
}: Props) {
  if (!visible) return null;

  return (
    <div
      className="mt-6 rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.08] px-4 py-4 text-center sm:px-5"
      role="status"
      aria-live="polite"
    >
      <p className="text-sm font-medium leading-relaxed text-emerald-100/95">{message}</p>
    </div>
  );
}
