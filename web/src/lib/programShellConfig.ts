import { isEscalationPath, isProgramPeripheralPath } from "@/lib/workflowStepRoutes";
import type { ProgramState } from "@/lib/programStateTypes";

/** 9 engine steps + follow-up column (escalation / optional next phase). */
export const PROGRAM_DISPLAY_TOTAL = 10;

export const PROGRAM_SHELL_TITLE = "Your Credit Dispute Program";

export type ProgramTimelineNode = {
  id: string;
  label: string;
  backendStepId?: string;
  routes: string[];
};

export const PROGRAM_TIMELINE: ProgramTimelineNode[] = [
  { id: "upload", label: "Upload", backendStepId: "upload", routes: ["/upload"] },
  { id: "analyze", label: "Analysis", backendStepId: "parse_analyze", routes: ["/analyze"] },
  /**
   * Review: server `currentStep` is the truth; `/upload`, `/analyze`, and `/prepare` are all
   * valid while `currentStep === "review_claims"`. `currentTimelineIndex` prefers `currentStep`
   * over the URL so the highlight stays on **Review** (not Upload/Analysis) on any of those paths.
   */
  {
    id: "review",
    label: "Review",
    backendStepId: "review_claims",
    routes: ["/prepare", "/analyze", "/upload"],
  },
  { id: "strategy", label: "Strategy", backendStepId: "select_disputes", routes: ["/strategy"] },
  { id: "payment", label: "Payment", backendStepId: "payment", routes: ["/payment"] },
  { id: "letters", label: "Letters", backendStepId: "letter_generation", routes: ["/letters"] },
  { id: "proof", label: "Proof", backendStepId: "proof_attachment", routes: ["/proof"] },
  { id: "mail", label: "Mail", backendStepId: "mail", routes: ["/send"] },
  { id: "track", label: "Tracking", backendStepId: "track", routes: ["/tracking"] },
  { id: "escalation", label: "Follow-up", routes: ["/escalation", "/escalation-action"] },
];

const FRAMING: Record<string, string> = {
  upload: "Add your report PDFs—this file stays in your private workspace only.",
  parse_analyze: "We analyzed your report and are organizing the clearest next actions.",
  review_claims: "We analyzed your report and found the best opportunities to focus on first.",
  select_disputes: "Review and confirm the disputes you want in this mailing round.",
  payment: "Complete this round’s access so we can generate your package.",
  letter_generation: "We’re preparing your letters for this round.",
  proof_attachment: "Attach the proof the mail path needs to send on your behalf.",
  mail: "Send certified disputes through the mail partner when you’re ready.",
  track: "Track sends and postmarks—responses connect back to your program.",
  escalation: "Optional next steps when bureau letters need more pressure.",
  responses: "Log what came back from the bureaus so the program stays accurate.",
  execute: "Quickly note how a step went—helps the program match reality.",
  report: "A read-only snapshot of your program. Your current step in the journey is below on the timeline.",
};

/**
 * Active timeline column: **backend `currentStep` wins** over the URL. Escalation routes
 * (see `isEscalationPath`) map to the follow-up column. Path-based fallback only applies when
 * `currentStep` is missing/unknown (see `review` multi-route note on `PROGRAM_TIMELINE`).
 */
export function currentTimelineIndex(
  programState: ProgramState | null | undefined,
  pathname: string,
): number {
  if (isEscalationPath(pathname)) return 9;
  if (isStructuredReportPath(pathname) && programState?.currentStep) {
    const j = PROGRAM_TIMELINE.findIndex((n) => n.backendStepId === programState.currentStep);
    if (j >= 0) return j;
  }
  const head = programState?.currentStep;
  if (head) {
    const j = PROGRAM_TIMELINE.findIndex((n) => n.backendStepId === head);
    if (j >= 0) return j;
  }
  for (let i = 0; i < PROGRAM_TIMELINE.length; i++) {
    const n = PROGRAM_TIMELINE[i];
    if (n.backendStepId && n.routes.some((r) => r === pathname)) return i;
  }
  for (let i = 0; i < PROGRAM_TIMELINE.length; i++) {
    const n = PROGRAM_TIMELINE[i];
    if (n.routes.some((r) => r === pathname)) return i;
  }
  return 0;
}

export function programHeaderCopy(
  programState: ProgramState | null,
  pathname: string,
): { index1: number; stepLabel: string; contextLine: string } {
  if (isEscalationPath(pathname)) {
    return {
      index1: 10,
      stepLabel: "Follow-up",
      contextLine: FRAMING.escalation,
    };
  }
  if (pathname === "/responses") {
    return {
      index1: 9,
      stepLabel: "Responses",
      contextLine: FRAMING.responses,
    };
  }
  if (pathname === "/execute") {
    return {
      index1: Math.min(9, programState?.progress.current ?? 6),
      stepLabel: "Check-in",
      contextLine: FRAMING.execute,
    };
  }
  if (isStructuredReportPath(pathname)) {
    if (!programState) {
      return {
        index1: 1,
        stepLabel: "Report",
        contextLine: FRAMING.report,
      };
    }
    if (programState.isComplete) {
      return {
        index1: PROGRAM_DISPLAY_TOTAL,
        stepLabel: "Report",
        contextLine: "This round is complete. Review what the system found and what was done so far.",
      };
    }
    const tIdx = currentTimelineIndex(programState, pathname);
    const index1 = Math.min(PROGRAM_DISPLAY_TOTAL, tIdx + 1);
    return {
      index1,
      stepLabel: "Report",
      contextLine: FRAMING.report,
    };
  }
  if (!programState) {
    return {
      index1: 1,
      stepLabel: "Upload",
      contextLine: FRAMING.upload,
    };
  }
  if (programState.isComplete) {
    return {
      index1: PROGRAM_DISPLAY_TOTAL,
      stepLabel: "Program round complete",
      contextLine: "This guided round is done—keep monitoring bureaus and inboxes.",
    };
  }
  const tIdx = currentTimelineIndex(programState, pathname);
  const node = PROGRAM_TIMELINE[tIdx] ?? PROGRAM_TIMELINE[0];
  const head = programState.currentStep ?? undefined;
  const index1 = Math.min(PROGRAM_DISPLAY_TOTAL, tIdx + 1);
  const key = (head ?? node.backendStepId ?? "upload") as string;
  return {
    index1,
    stepLabel: node.label,
    contextLine: FRAMING[key] ?? "Work through this step; your program advances when the system confirms it.",
  };
}

export function reportEntryHref(
  programState: ProgramState | null,
  pathname: string,
): { to: string; label: string } {
  if (pathname === "/report") {
    return { to: "/report", label: "Viewing report" };
  }
  if (programState) {
    return { to: "/report", label: "Structured report" };
  }
  if (pathname === "/upload") {
    return { to: "/upload", label: "View upload" };
  }
  return { to: "/upload", label: "Structured report (after setup)" };
}

export function shouldShowProgramShell(workflowId: string | null, pathname: string): boolean {
  return Boolean(workflowId) && !pathname.startsWith("/program");
}

export function isStructuredReportPath(pathname: string): boolean {
  return pathname === "/report";
}

export function isPeripheralForShell(path: string): boolean {
  return (
    isProgramPeripheralPath(path) || isEscalationPath(path) || isStructuredReportPath(path)
  );
}
