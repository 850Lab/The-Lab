import type { ReactNode } from "react";

type Tone = "neutral" | "ok" | "warn" | "bad" | "info";

const tones: Record<Tone, string> = {
  neutral:
    "border-white/15 bg-lab-elevated text-lab-muted",
  ok: "border-emerald-500/40 bg-emerald-950/50 text-emerald-200",
  warn: "border-amber-500/40 bg-amber-950/40 text-amber-100",
  bad: "border-red-500/40 bg-red-950/50 text-red-200",
  info: "border-sky-500/40 bg-sky-950/40 text-sky-100",
};

export function McStatusChip({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide border ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
