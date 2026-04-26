/**
 * When GET /program-state is unavailable (5xx, ok:false, or network error), derive a safe
 * ProgramState from the resume envelope so the app shell and routes still work.
 */
import type { ProgramState, ProgramStateProgress } from "@/lib/programStateTypes";
import type { WorkflowIntegrityHints } from "@/lib/integrityHintsTypes";
import {
  BACKEND_LINEAR_STEP_ORDER,
  type BackendWorkflowStepId,
  computeAuthoritativeStep,
  customerRouteForBackendStep,
} from "@/lib/workflowStepRoutes";
import type { WorkflowEnvelope, WorkflowStepStatusRow } from "@/lib/workflowTypes";

const FALLBACK_VERSION = "envelope_fallback_v1";

function allowedNavRoutesFallback(
  head: string | null,
  phase: "active" | "done",
  mailBlocked: boolean,
): string[] {
  if (phase === "done" || !head) {
    return ["/tracking"];
  }
  if (head === "review_claims") {
    return ["/prepare", "/analyze", "/upload"];
  }
  if (head === "mail" && mailBlocked) {
    return ["/send", "/tracking"];
  }
  return [customerRouteForBackendStep(head, "active")];
}

function buildProgressFallback(stepStatus: WorkflowStepStatusRow[]): ProgramStateProgress {
  const order = [...BACKEND_LINEAR_STEP_ORDER];
  const smap: Record<string, { status?: string }> = {};
  for (const row of stepStatus) {
    smap[row.stepId] = row;
  }
  const completed: string[] = [];
  for (const sid of order) {
    if (String((smap[sid] as { status?: string } | undefined)?.status) === "completed") {
      completed.push(sid);
    }
  }
  let head: string | null = null;
  for (const sid of order) {
    if (String((smap[sid] as { status?: string } | undefined)?.status) !== "completed") {
      head = sid;
      break;
    }
  }
  const n = order.length;
  const hIdx = head ? order.indexOf(head as BackendWorkflowStepId) : -1;
  const current1b = hIdx >= 0 ? hIdx + 1 : n;
  const upcoming: string[] = [];
  if (hIdx >= 0) {
    for (let j = hIdx + 1; j < n; j++) {
      const sid = order[j];
      if (String((smap[sid] as { status?: string } | undefined)?.status) !== "completed") {
        upcoming.push(sid);
      }
    }
  }
  return {
    current: current1b,
    total: n,
    completedSteps: completed,
    upcomingSteps: upcoming,
  };
}

/**
 * Synthesizes ProgramState from resume + integrity hints when the program-state API fails.
 * Keeps ORION, shell, and guards functional without the authoritative JSON.
 */
export function buildFallbackProgramState(
  env: WorkflowEnvelope,
  workflowId: string,
  hints: WorkflowIntegrityHints | null,
): ProgramState {
  const { stepId, phase } = computeAuthoritativeStep(env.stepStatus ?? []);
  const isComplete = phase === "done";
  const mailBlocked = hints?.mailBlocked === true;
  const canonical = customerRouteForBackendStep(stepId, phase);
  const allowed = allowedNavRoutesFallback(stepId, phase, mailBlocked);
  const label = isComplete ? "View tracking" : "Continue your program";
  return {
    version: FALLBACK_VERSION,
    workflowId,
    currentStep: stepId,
    stepStatus: null,
    canonicalRoute: canonical,
    allowedNavRoutes: allowed,
    nextBestAction: {
      label,
      description: "",
      targetRoute: canonical,
      required: !isComplete,
    },
    progress: buildProgressFallback(env.stepStatus ?? []),
    blockingIssues: [],
    isComplete,
  };
}
