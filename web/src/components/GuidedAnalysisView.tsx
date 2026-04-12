import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import type { ReportIntakeRow } from "@/lib/intakeTypes";

const CUES = [
  "Reading your report…",
  "Reviewing accounts and payment history…",
  "Identifying items that may need attention…",
  "Preparing your findings…",
] as const;

const ROTATE_MS = 4500;

type Props = {
  /** From navigation state right after upload, until intake poll returns. */
  fileNameHint: string | null;
  /** Primary report row from backend intake when available. */
  primaryReport: ReportIntakeRow | null;
  /** True when analysis has run longer than expected (UX only; step still in flight per backend). */
  showSlowHint: boolean;
};

function displayFileName(primary: ReportIntakeRow | null, hint: string | null): string {
  const fn = primary?.fileName?.trim();
  if (fn) return fn;
  if (hint?.trim()) return hint.trim();
  return "Your credit report";
}

function displayBureau(primary: ReportIntakeRow | null): string | null {
  const b = primary?.bureau?.trim();
  if (!b || b === "unknown") return null;
  return b.charAt(0).toUpperCase() + b.slice(1);
}

export function GuidedAnalysisView({
  fileNameHint,
  primaryReport,
  showSlowHint,
}: Props) {
  const [cueIdx, setCueIdx] = useState(0);
  const fileLabel = displayFileName(primaryReport, fileNameHint);
  const bureau = displayBureau(primaryReport);

  useEffect(() => {
    const id = window.setInterval(() => {
      setCueIdx((i) => (i + 1) % CUES.length);
    }, ROTATE_MS);
    return () => window.clearInterval(id);
  }, []);

  return (
    <div className="mx-auto max-w-lg">
      <h2 className="text-center text-xl font-semibold tracking-tight text-lab-text sm:text-2xl">
        We&apos;re reading your report
      </h2>
      <ProgramFlowBridge className="mx-auto mt-4 max-w-md">
        <span className="font-medium text-lab-text">Now that your report is uploaded,</span> we&apos;re
        analyzing it on your behalf. Stay on this screen — when the server finishes, findings appear
        in the same flow (no new tab, no jumping around).
      </ProgramFlowBridge>

      <p className="mx-auto mt-4 max-w-md text-center text-sm leading-relaxed text-lab-muted">
        You don&apos;t need to do anything here. Same analysis path the rest of your program uses.
      </p>

      <div className="mt-8 rounded-2xl border border-white/[0.1] bg-lab-surface/70 p-4 sm:p-5">
        <div className="flex gap-4">
          <div
            className="relative flex h-36 w-[7.5rem] shrink-0 flex-col items-center justify-center rounded-xl border border-white/[0.08] bg-gradient-to-b from-lab-elevated to-lab-surface sm:h-40 sm:w-[8.5rem]"
            aria-hidden
          >
            <span className="text-[10px] font-semibold uppercase tracking-wider text-lab-subtle">
              PDF
            </span>
            <div className="mt-2 h-8 w-8 rounded-full border-2 border-lab-accent/35 border-t-lab-accent animate-spin" />
          </div>
          <div className="min-w-0 flex-1 text-left">
            <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">On file</p>
            <p className="mt-1 break-words text-sm font-medium text-lab-text">{fileLabel}</p>
            {bureau ? (
              <p className="mt-1 text-xs text-lab-muted">Bureau: {bureau}</p>
            ) : (
              <p className="mt-1 text-xs text-lab-muted">We&apos;ll confirm bureau details as we parse.</p>
            )}
          </div>
        </div>
      </div>

      <div
        className="mt-8 min-h-[3.5rem] text-center"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        <AnimatePresence mode="wait">
          <motion.p
            key={cueIdx}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.35 }}
            className="text-sm leading-relaxed text-lab-muted"
          >
            {CUES[cueIdx]}
          </motion.p>
        </AnimatePresence>
      </div>

      {showSlowHint ? (
        <p className="mt-6 text-center text-xs leading-relaxed text-lab-subtle">
          This is taking longer than usual — we&apos;re still working. If nothing changes after a few
          minutes, refresh the page once; you won&apos;t lose your upload.
        </p>
      ) : (
        <p className="mt-6 text-center text-xs text-lab-subtle">
          This page updates automatically when analysis finishes.
        </p>
      )}
    </div>
  );
}
