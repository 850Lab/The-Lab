/**
 * Maps backend workflow step IDs (services.workflow.registry.LINEAR_STEP_ORDER)
 * to customer React routes. Keep aligned with Python registry.
 */

import type { NextRequiredAction } from "@/lib/integrityHintsTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export const BACKEND_LINEAR_STEP_ORDER = [
  "upload",
  "parse_analyze",
  "review_claims",
  "select_disputes",
  "payment",
  "letter_generation",
  "proof_attachment",
  "mail",
  "track",
] as const;

export type BackendWorkflowStepId = (typeof BACKEND_LINEAR_STEP_ORDER)[number];

const BACKEND_STEP_TO_CUSTOMER_ROUTE: Record<BackendWorkflowStepId, string> = {
  upload: "/upload",
  parse_analyze: "/analyze",
  review_claims: "/prepare",
  select_disputes: "/strategy",
  payment: "/payment",
  letter_generation: "/letters",
  proof_attachment: "/proof",
  mail: "/send",
  track: "/tracking",
};

/** Funnel paths that must match backend authoritative step when a workflow is loaded. */
export const CUSTOMER_WORKFLOW_GUARD_PATHS: ReadonlySet<string> = new Set([
  "/",
  "/upload",
  "/analyze",
  "/prepare",
  "/strategy",
  "/payment",
  "/letters",
  "/proof",
  "/send",
  "/tracking",
]);

export function customerRouteForBackendStep(
  stepId: string | null,
  phase: "active" | "done",
): string {
  if (phase === "done" || !stepId) return "/tracking";
  const route =
    BACKEND_STEP_TO_CUSTOMER_ROUTE[stepId as BackendWorkflowStepId];
  return route ?? "/tracking";
}

export function computeAuthoritativeStep(
  stepStatus: Array<{ stepId: string; status: string }>,
): { stepId: string | null; phase: "active" | "done" } {
  const map = new Map(stepStatus.map((s) => [s.stepId, s.status]));
  for (const sid of BACKEND_LINEAR_STEP_ORDER) {
    const st = map.get(sid);
    if (st === undefined) continue;
    if (st === "completed") continue;
    return { stepId: sid, phase: "active" };
  }
  return { stepId: null, phase: "done" };
}

export function isEscalationPath(pathname: string): boolean {
  return (
    pathname === "/escalation" ||
    pathname === "/escalation-action" ||
    pathname.startsWith("/escalation/")
  );
}

/** Customer route matching backend authoritative step from a workflow API envelope. */
export function customerPathFromEnvelope(env: WorkflowEnvelope): string {
  const a = computeAuthoritativeStep(env.stepStatus ?? []);
  return customerRouteForBackendStep(a.stepId, a.phase);
}

/** True when the engine's current step is earlier than ``thanStep`` in the linear registry. */
/** Stable route for coarse `nextRequiredAction` from GET /integrity-hints (pre-pay uses ``canonical``). */
export function customerPathForNextRequiredAction(
  action: NextRequiredAction,
  canonicalCustomerPath: string,
): string {
  switch (action) {
    case "proof":
      return "/proof";
    case "pay":
      return "/payment";
    case "generate":
      return "/letters";
    case "mail":
      return "/send";
    case "track":
      return "/tracking";
    case "upload":
    default:
      return canonicalCustomerPath;
  }
}

export function isAuthoritativeStepBefore(
  stepId: string | null,
  thanStep: BackendWorkflowStepId,
): boolean {
  if (!stepId) return false;
  const order = BACKEND_LINEAR_STEP_ORDER;
  const i = order.indexOf(stepId as BackendWorkflowStepId);
  const j = order.indexOf(thanStep);
  if (i < 0 || j < 0) return false;
  return i < j;
}
