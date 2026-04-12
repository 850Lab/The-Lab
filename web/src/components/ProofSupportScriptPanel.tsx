import { useLayoutEffect, useRef, useEffect } from "react";
import {
  ORION_PROOF_SCRIPT_RENDERED,
  ORION_PROOF_SCRIPT_VISIBLE,
  type OrionProofSignalContext,
  sendOrionProofSignal,
} from "@/lib/orionProofSignals";
import { safeCustomerProofSupportScript } from "@/lib/proofSupportingAiScript";

type Props = {
  aiScript: unknown;
  /** When set, emits ORION V2.4 observability signals (non-blocking). */
  signalContext?: OrionProofSignalContext | null;
};

/**
 * Secondary support wording for proof verification — below deterministic ORION and “More context”.
 */
export function ProofSupportScriptPanel({ aiScript, signalContext }: Props) {
  const script = safeCustomerProofSupportScript(aiScript);
  const rootRef = useRef<HTMLDivElement>(null);
  const renderedSent = useRef(false);
  const visibleSent = useRef(false);

  useEffect(() => {
    if (!script || !signalContext || renderedSent.current) return;
    renderedSent.current = true;
    sendOrionProofSignal(signalContext, ORION_PROOF_SCRIPT_RENDERED);
  }, [script, signalContext]);

  useLayoutEffect(() => {
    if (!script || !signalContext || visibleSent.current) return;
    if (typeof IntersectionObserver === "undefined") return;
    const el = rootRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        const e = entries[0];
        if (!e?.isIntersecting || e.intersectionRatio < 0.5) return;
        if (visibleSent.current) return;
        visibleSent.current = true;
        sendOrionProofSignal(signalContext, ORION_PROOF_SCRIPT_VISIBLE);
        obs.disconnect();
      },
      { threshold: [0.5] },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [script, signalContext]);

  if (!script) return null;

  return (
    <div ref={rootRef} className="mx-auto mt-3 max-w-lg rounded-lg border border-white/[0.06] bg-lab-surface/35 px-3.5 py-3 sm:px-4">
      <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
        Suggested wording
      </p>
      <p className="mt-1.5 text-[13px] font-medium leading-snug text-lab-text sm:text-sm">
        {script.title}
      </p>
      {script.intro ? (
        <p className="mt-1.5 text-[13px] leading-snug text-lab-muted sm:text-sm">{script.intro}</p>
      ) : null}
      {script.lines.length > 0 ? (
        <ul className="mt-2 space-y-1.5 text-[12px] leading-snug text-lab-muted sm:text-[13px]">
          {script.lines.map((ln, i) => (
            <li key={i} className="flex gap-1.5">
              <span className="mt-0.5 shrink-0 text-lab-accent/70" aria-hidden>
                •
              </span>
              <span className="italic text-lab-text/95">&ldquo;{ln.text}&rdquo;</span>
            </li>
          ))}
        </ul>
      ) : null}
      {script.talkingPoints.length > 0 ? (
        <ul className="mt-2 space-y-1 text-[12px] leading-snug text-lab-muted sm:text-[13px]">
          {script.talkingPoints.map((tp, i) => (
            <li key={i} className="flex gap-1.5">
              <span className="mt-0.5 shrink-0 text-lab-subtle" aria-hidden>
                –
              </span>
              <span>{tp}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
