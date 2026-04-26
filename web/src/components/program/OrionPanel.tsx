import { useEffect, useState } from "react";
import type { OrionMode } from "@/lib/orion/orionBehavior";
import type { OrionCaseStripItem } from "@/lib/orion/orionCaseStrip";
import type { OrionSurfacePayload } from "@/providers/OrionSystemContext";

const ROTATE_MS = 3000;

function modeWorking(mode: OrionMode): boolean {
  return mode === "working";
}

function OrionAbstractInsignia() {
  return (
    <div
      className="relative mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-slate-500/30 bg-zinc-900/90"
      aria-hidden
    >
      <div className="absolute inset-[5px] rounded-sm border border-slate-400/20" />
      <div className="flex gap-0.5">
        <span className="h-4 w-0.5 rounded-full bg-slate-400/50" />
        <span className="h-4 w-0.5 rounded-full bg-slate-500/35" />
        <span className="h-4 w-0.5 rounded-full bg-slate-500/25" />
      </div>
    </div>
  );
}

function OrionCaseStatusStrip({ items }: { items: OrionCaseStripItem[] }) {
  return (
    <div className="border-t border-slate-700/50 pt-3" aria-label="Case progress">
      <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">Case status</p>
      <ul className="mt-2 space-y-1.5">
        {items.map((row) => (
          <li
            key={row.id}
            className={[
              "flex items-center gap-2 text-[11px] leading-tight transition-colors duration-200",
              row.tone === "complete" ? "text-slate-500" : "",
              row.tone === "current" ? "font-medium text-slate-100" : "",
              row.tone === "upcoming" ? "text-zinc-600" : "",
            ].join(" ")}
          >
            <span
              className={[
                "inline-flex h-1.5 w-1.5 shrink-0 rounded-full",
                row.tone === "complete" ? "bg-slate-500/70" : "",
                row.tone === "current" ? "bg-slate-300 shadow-[0_0_0_1px_rgba(148,163,184,0.35)]" : "",
                row.tone === "upcoming" ? "bg-zinc-700" : "",
              ].join(" ")}
              aria-hidden
            />
            <span>{row.label}</span>
            {row.tone === "complete" ? (
              <span className="ml-auto text-[9px] font-medium uppercase tracking-wide text-slate-500">
                Done
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function OrionPanel({ model }: { model: OrionSurfacePayload }) {
  const { behavior, caseStrip, accentLine, rotatingOverride, stateKey, nextActionOverride } = model;
  const rotating = rotatingOverride ?? behavior.rotating;
  const working = modeWorking(behavior.mode);
  const showRotating = working && Boolean(rotating?.length);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!showRotating || !rotating?.length) return;
    setIndex(0);
    const interval = setInterval(() => {
      setIndex((i) => (i + 1) % rotating.length);
    }, ROTATE_MS);
    return () => clearInterval(interval);
  }, [rotating, showRotating, stateKey]);

  const rotatingLine =
    showRotating && rotating && rotating.length > 0 ? rotating[index % rotating.length] : null;

  const statusUpper = behavior.status.toUpperCase();
  const nextActionText = nextActionOverride ?? behavior.nextAction;

  return (
    <aside
      className={[
        "overflow-hidden rounded-xl border border-slate-700/60 bg-zinc-950 shadow-[0_16px_48px_rgba(0,0,0,0.5)] transition-opacity duration-300 ease-out",
        working ? "orion-rail--working" : "",
      ].join(" ")}
      data-orion-state={stateKey}
    >
      <style>{`
        .orion-rail--working .orion-rail__activity-dot {
          animation: orionDotPulse 2.2s ease-in-out infinite;
        }
        .orion-rail--working .orion-rail__activity-line {
          animation: orionLinePulse 2.2s ease-in-out infinite;
        }
        @keyframes orionDotPulse {
          0%, 100% { opacity: 0.35; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.08); }
        }
        @keyframes orionLinePulse {
          0%, 100% { opacity: 0.2; }
          50% { opacity: 0.65; }
        }
      `}</style>

      {working ? (
        <div
          className="orion-rail__activity-line h-px w-full bg-gradient-to-r from-transparent via-slate-400/40 to-transparent"
          aria-hidden
        />
      ) : (
        <div className="h-px w-full bg-slate-800/60" aria-hidden />
      )}

      <div className="border-b border-slate-800/80 px-4 py-3.5">
        <div className="flex items-start gap-3">
          <OrionAbstractInsignia />
          <div className="min-w-0 pt-0.5">
            <p className="text-[11px] font-semibold tracking-[0.22em] text-slate-100">ORION</p>
            <p className="mt-0.5 text-[10px] font-medium tracking-wide text-slate-500">Case Guide</p>
          </div>
        </div>
      </div>

      <div
        key={stateKey}
        className="space-y-3.5 px-4 py-4 transition-opacity duration-200 ease-out"
      >
        <div className="flex items-start gap-2">
          {working ? (
            <span
              className="orion-rail__activity-dot mt-1 inline-flex h-2 w-2 shrink-0 rounded-full bg-slate-400/90"
              aria-hidden
            />
          ) : null}
          <p
            className={[
              "min-w-0 flex-1 text-[10px] font-semibold uppercase leading-snug tracking-[0.18em] text-slate-400",
              working ? "text-slate-400/95" : "",
            ].join(" ")}
          >
            {statusUpper}
          </p>
        </div>

        <p className="text-sm font-medium leading-snug text-slate-50">{behavior.message}</p>

        {!working && behavior.sub ? (
          <p className="text-xs leading-relaxed text-slate-500">{behavior.sub}</p>
        ) : null}

        {!showRotating && accentLine ? (
          <p className="border-l-2 border-slate-500/40 pl-3 text-xs leading-relaxed text-slate-400">
            {accentLine}
          </p>
        ) : null}

        {showRotating && rotatingLine ? (
          <p className="text-[11px] font-medium leading-relaxed text-slate-500" aria-live="polite" aria-atomic="true">
            {rotatingLine}
          </p>
        ) : null}

        {nextActionText ? (
          <div className="rounded-lg border border-slate-600/35 bg-zinc-900/80 px-3 py-2.5 shadow-inner shadow-black/20">
            <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              Next action
            </p>
            <p className="mt-1 text-xs font-medium leading-snug text-slate-200">{nextActionText}</p>
          </div>
        ) : null}
      </div>

      <div className="px-4 pb-4">
        <OrionCaseStatusStrip items={caseStrip} />
      </div>
    </aside>
  );
}
