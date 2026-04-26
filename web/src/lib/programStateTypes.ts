/**
 * Authoritative program brain — mirrors GET /api/workflows/{id}/program-state (backend-only).
 */

export type ProgramStateBlockingIssue = {
  code: string;
  message: string;
  severity: "error" | "warning";
};

export type ProgramStateNextBestAction = {
  label: string;
  description: string;
  targetRoute: string;
  required: boolean;
};

export type ProgramStateProgress = {
  current: number;
  total: number;
  completedSteps: string[];
  upcomingSteps: string[];
};

export type ProgramState = {
  version: string;
  workflowId: string;
  currentStep: string | null;
  stepStatus: string | null;
  canonicalRoute: string;
  allowedNavRoutes: string[];
  nextBestAction: ProgramStateNextBestAction;
  progress: ProgramStateProgress;
  blockingIssues: ProgramStateBlockingIssue[];
  isComplete: boolean;
};

export type ProgramStateErrorBody = { code: string; messageSafe?: string };

export type ProgramStateResponse =
  | (ProgramState & { ok: true })
  | { ok: false; version: string; error: ProgramStateErrorBody };

export function isProgramStateOk(
  r: ProgramStateResponse,
): r is ProgramState & { ok: true } {
  return (r as { ok?: boolean }).ok === true;
}
