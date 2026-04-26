import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { ProgramNextActionBar } from "@/components/ProgramNextActionBar";
import { ProgramTimeline } from "@/components/ProgramTimeline";
import {
  PROGRAM_DISPLAY_TOTAL,
  PROGRAM_SHELL_TITLE,
  isPeripheralForShell,
  programHeaderCopy,
  reportEntryHref,
} from "@/lib/programShellConfig";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

type Props = {
  children: ReactNode;
};

/**
 * Unified step shell: program header, read-only timeline, main outlet, one bottom CTA when server routes ahead.
 * Side task: "View full report" stays secondary; does not take focus from the step.
 */
export function ProgramShellFrame({ children }: Props) {
  const path = useLocation().pathname;
  const { programState, workflowId } = useCustomerWorkflow();
  if (!workflowId) return <>{children}</>;
  const peripheral = isPeripheralForShell(path);
  const { index1, stepLabel, contextLine } = programHeaderCopy(programState, path);
  const { to: reportTo, label: reportLabel } = reportEntryHref(programState, path);
  const onReport = path === reportTo;
  return (
    <div
      className="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col gap-0 px-4 pb-6 pt-14 sm:px-5"
      data-program-shell={peripheral ? "peripheral" : "core"}
    >
      <header className="shrink-0 space-y-2 border-b border-white/[0.06] pb-3">
        <p className="text-[0.7rem] font-medium uppercase tracking-[0.14em] text-lab-subtle/80">
          {PROGRAM_SHELL_TITLE}
        </p>
        <p className="text-[0.7rem] font-medium text-lab-subtle/90" aria-label="Step position in program">
          Step {index1} of {PROGRAM_DISPLAY_TOTAL}
        </p>
        <h1 className="text-balance text-lg font-semibold tracking-tight text-lab-text sm:text-xl">
          {stepLabel}
        </h1>
        <p className="text-xs leading-snug text-lab-subtle sm:text-sm">{contextLine}</p>
        {reportLabel ? (
          <p className="pt-0.5">
            {onReport ? (
              <span
                className="text-xs text-lab-subtle/70"
                title="This view is current"
              >
                {reportLabel}
                <span className="pl-1 text-lab-subtle/50">(this view)</span>
              </span>
            ) : (
              <Link
                to={reportTo}
                className="text-xs font-medium text-lab-accent/90 underline decoration-lab-accent/35 underline-offset-2 hover:decoration-lab-accent/70"
                data-secondary-flow="report"
              >
                {reportLabel}
              </Link>
            )}
          </p>
        ) : null}
        <ProgramTimeline programState={programState} />
      </header>
      <div className="min-h-0 flex-1 pt-1 sm:pt-2">{children}</div>
      <footer className="shrink-0" data-program-next-region>
        <ProgramNextActionBar />
      </footer>
    </div>
  );
}
