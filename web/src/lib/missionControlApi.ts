const LS_KEY = "mcc_admin_key";

/** Fired after `setMissionControlAdminKey` so Mission Control views can refetch without a full reload. */
export const MCC_ADMIN_KEY_CHANGE_EVENT = "mcc-admin-key-changed";

export function getMissionControlAdminKey(): string {
  if (typeof localStorage === "undefined") return "";
  return (
    localStorage.getItem(LS_KEY) ||
    import.meta.env.VITE_WORKFLOW_ADMIN_KEY ||
    ""
  ).trim();
}

export function setMissionControlAdminKey(key: string): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(LS_KEY, key.trim());
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(MCC_ADMIN_KEY_CHANGE_EVENT));
  }
}

/**
 * Workflow API base URL (no trailing slash).
 * - Replit / local Vite dev: default `/workflow-api` → dev-server proxy → uvicorn :8000.
 * - Cross-origin (e.g. preview on another port): set `VITE_WORKFLOW_API_URL` in Secrets / `.env`
 *   to the public origin of the FastAPI app (e.g. `https://<repl>-8000.<host>`).
 * - Path prefix only: `VITE_WORKFLOW_API_PREFIX` (overrides default path when URL not set).
 */
function apiBase(): string {
  const absolute = (
    import.meta.env.VITE_WORKFLOW_API_URL as string | undefined
  )?.trim();
  if (absolute) return absolute.replace(/\/$/, "");

  const prefix = (
    import.meta.env.VITE_WORKFLOW_API_PREFIX as string | undefined
  )?.trim();
  if (prefix) return prefix.replace(/\/$/, "");

  return "/workflow-api";
}

export class MissionControlApiError extends Error {
  status: number;
  body: string;
  constructor(status: number, body: string) {
    super(`Mission Control API ${status}: ${body.slice(0, 200)}`);
    this.status = status;
    this.body = body;
  }
}

export async function mccGet<T = unknown>(path: string): Promise<T> {
  const key = getMissionControlAdminKey();
  const url = `${apiBase()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "GET",
    headers: {
      ...(key ? { "X-Workflow-Admin-Key": key } : {}),
    },
  });
  const text = await res.text();
  if (!res.ok) {
    throw new MissionControlApiError(res.status, text);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new MissionControlApiError(res.status, "Invalid JSON response");
  }
}

/** Rows from ``GET /internal/admin/demo-leads`` (snake_case from API). */
export type MissionControlDemoLeadRow = {
  id: number;
  name: string;
  email: string;
  phone: string | null;
  source: string;
  scenario_id: string | null;
  workflow_id: string | null;
  created_at: string;
  meta?: Record<string, unknown>;
  converted_organization_id?: number | null;
  lead_disposition?: string | null;
};

export async function mccFetchDemoLeads(
  limit = 200,
): Promise<MissionControlDemoLeadRow[]> {
  const cap = Math.max(1, Math.min(500, limit));
  const data = await mccGet<{ demoLeads: MissionControlDemoLeadRow[] }>(
    `/internal/admin/demo-leads?limit=${cap}`,
  );
  return data.demoLeads ?? [];
}

export async function mccConvertDemoLeadToOrg(
  leadId: number,
  organizationName: string,
): Promise<{ ok: boolean; leadId: number; organization: { id: number; name?: string } }> {
  return mccPost(`/internal/admin/demo-leads/${leadId}/convert-to-org`, {
    organizationName,
  });
}

/** Rows from ``GET /internal/admin/workflows/{id}/events`` */
export type McWorkflowEventRow = {
  id: string;
  workflowId: string;
  eventType: string;
  stepId: string | null;
  previousState: unknown;
  newState: unknown;
  actor: string;
  source: string;
  metadata: Record<string, unknown>;
  createdAt: string | null;
};

export async function mccFetchWorkflowEvents(
  workflowId: string,
  limit = 500,
): Promise<McWorkflowEventRow[]> {
  const cap = Math.max(1, Math.min(2000, limit));
  const data = await mccGet<{
    ok?: boolean;
    items?: McWorkflowEventRow[];
  }>(
    `/internal/admin/workflows/${encodeURIComponent(workflowId)}/events?limit=${cap}`,
  );
  if (data && typeof data === "object" && data.ok === false) return [];
  return data.items ?? [];
}

export function formatMccErrorMessage(err: unknown): string {
  if (err instanceof MissionControlApiError) {
    return parseFastApiDetail(err.body) || err.message;
  }
  if (err instanceof Error) return err.message;
  return String(err);
}

function parseFastApiDetail(body: string): string | null {
  try {
    const j = JSON.parse(body) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((x: { msg?: string; loc?: unknown }) => x.msg || JSON.stringify(x))
        .join("; ");
    }
    if (d && typeof d === "object") {
      const o = d as Record<string, unknown>;
      if (typeof o.messageSafe === "string") return o.messageSafe;
      if (typeof o.message === "string") return o.message;
      if (typeof o.code === "string") return o.code;
    }
  } catch {
    /* ignore */
  }
  return body.trim() ? body.slice(0, 800) : null;
}

export type ArchitectScenarioRow = {
  id: string;
  label: string;
  persona: string;
  launchPath: string;
  description: string;
  fixtureHint?: string;
};

export type ArchitectApplyResult = {
  ok: boolean;
  scenarioId?: string;
  fixtureHint?: string;
  sessionToken: string;
  launchPath: string;
  user: {
    id: number;
    email: string;
    displayName?: string | null;
    platformRole?: string;
  };
  persona: string;
  membershipRole: string | null;
  organizationId: number | null;
  enrollmentId: number | null;
  programWorkflowId: string | null;
  workshopSessionId?: number;
  consumerWorkflow?: {
    workflowId: string;
    currentStep: string | null;
    linearPhase: string;
    overallStatus: string | null;
    workflowType?: string | null;
  } | null;
};

export async function mccFetchArchitectScenarios(): Promise<ArchitectScenarioRow[]> {
  const data = await mccGet<{ ok?: boolean; scenarios?: ArchitectScenarioRow[] }>(
    "/internal/admin/architect-access/scenarios",
  );
  return data.scenarios ?? [];
}

export async function mccApplyArchitectScenario(body: {
  scenarioId: string;
  resetConsumerWorkflow?: boolean;
}): Promise<ArchitectApplyResult> {
  return mccPost<ArchitectApplyResult>("/internal/admin/architect-access/apply", {
    scenarioId: body.scenarioId,
    resetConsumerWorkflow: body.resetConsumerWorkflow ?? true,
  });
}

export async function mccPost<T = unknown>(
  path: string,
  body: unknown,
): Promise<T> {
  const key = getMissionControlAdminKey();
  const url = `${apiBase()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "X-Workflow-Admin-Key": key } : {}),
    },
    body: body === undefined ? "{}" : JSON.stringify(body),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new MissionControlApiError(res.status, text);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new MissionControlApiError(res.status, "Invalid JSON response");
  }
}

/** When the HTTP layer succeeds but the workflow API returns `{ ok: false, error }`. */
export function assertMccBusinessOk(res: unknown): void {
  if (!res || typeof res !== "object") return;
  const r = res as Record<string, unknown>;
  if (r.ok !== false) return;
  const e = r.error as Record<string, unknown> | undefined;
  const msg =
    (typeof e?.messageSafe === "string" && e.messageSafe) ||
    (typeof e?.code === "string" && e.code) ||
    (e && JSON.stringify(e)) ||
    "Action failed (ok: false).";
  throw new Error(msg);
}

export type McAuditFields = { actor_source: string; reason_safe: string };

export async function adminReopenStep(
  workflowId: string,
  body: McAuditFields & { step_id: string },
) {
  const res = await mccPost(`/internal/admin/workflows/${workflowId}/reopen-step`, {
    step_id: body.step_id,
    actor_source: body.actor_source,
    reason_safe: body.reason_safe,
  });
  assertMccBusinessOk(res);
  return res;
}

export async function adminPaymentWaived(
  workflowId: string,
  body: McAuditFields,
) {
  const res = await mccPost(
    `/internal/admin/workflows/${workflowId}/payment-waived`,
    body,
  );
  assertMccBusinessOk(res);
  return res;
}

export async function adminClearStalled(
  workflowId: string,
  body: McAuditFields,
) {
  const res = await mccPost(
    `/internal/admin/workflows/${workflowId}/clear-stalled-flag`,
    body,
  );
  assertMccBusinessOk(res);
  return res;
}

export async function adminRecoveryRetryStep(
  workflowId: string,
  body: McAuditFields & { user_id: number; step_id: string },
) {
  const res = await mccPost(
    `/internal/admin/workflows/${workflowId}/recovery/retry-step`,
    {
      user_id: body.user_id,
      step_id: body.step_id,
      actor_source: body.actor_source,
      reason_safe: body.reason_safe,
    },
  );
  assertMccBusinessOk(res);
  return res;
}

export async function adminRecoveryResumeCurrent(
  workflowId: string,
  body: McAuditFields & { user_id: number },
) {
  const res = await mccPost(
    `/internal/admin/workflows/${workflowId}/recovery/resume-current-step`,
    {
      user_id: body.user_id,
      actor_source: body.actor_source,
      reason_safe: body.reason_safe,
    },
  );
  assertMccBusinessOk(res);
  return res;
}

export async function adminRecoveryMailRetry(
  workflowId: string,
  body: McAuditFields & { user_id: number },
) {
  const res = await mccPost(
    `/internal/admin/workflows/${workflowId}/recovery/re-run-mail-attempt`,
    {
      user_id: body.user_id,
      actor_source: body.actor_source,
      reason_safe: body.reason_safe,
    },
  );
  assertMccBusinessOk(res);
  return res;
}

export async function adminOverrideClassification(body: {
  response_id: string;
  new_classification: string;
  reasoning_safe: string;
  actor_source: string;
  reason_safe: string;
}) {
  const res = await mccPost("/internal/admin/responses/override-classification", body);
  assertMccBusinessOk(res);
  return res;
}

export async function adminOverrideEscalation(body: {
  response_id: string;
  escalation_recommendation: Record<string, unknown>;
  actor_source: string;
  reason_safe: string;
}) {
  const res = await mccPost("/internal/admin/responses/override-escalation", body);
  assertMccBusinessOk(res);
  return res;
}

export async function adminSkipReminder(
  reminderId: string,
  body: McAuditFields,
) {
  const res = await mccPost(
    `/internal/admin/reminders/${reminderId}/skip`,
    body,
  );
  assertMccBusinessOk(res);
  return res;
}

export async function adminQueueReminderMc(reminderId: string) {
  const res = await mccPost(
    `/internal/admin/mission-control/reminders/${reminderId}/queue`,
    {},
  );
  assertMccBusinessOk(res);
  return res;
}

export async function adminDeliverReminderMc(reminderId: string) {
  const res = await mccPost(
    `/internal/admin/mission-control/reminders/${reminderId}/deliver`,
    {},
  );
  assertMccBusinessOk(res);
  return res;
}

export async function adminCreateReminderCandidatesMc(workflowId: string) {
  const res = await mccPost(
    `/internal/admin/mission-control/workflows/${workflowId}/reminder-candidates`,
    {},
  );
  assertMccBusinessOk(res);
  return res;
}
