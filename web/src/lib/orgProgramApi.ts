import { workflowApiBase } from "@/lib/apiBase";
import { formatReportUploadErrorMessage } from "@/lib/uploadHttpError";
import type {
  DisputeOptionsResponse,
  FindingsResponse,
  GenerateLettersResponse,
  OrgProgramResponse,
  ProgressResponse,
  ReportUploadResponse,
} from "@/lib/orgProgramTypes";

function parseDetailMessage(text: string): string {
  try {
    const j = JSON.parse(text) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "object" && d && "messageSafe" in d) {
      return String((d as { messageSafe: string }).messageSafe);
    }
    if (typeof d === "string") return d;
  } catch {
    /* keep slice */
  }
  return text.slice(0, 500);
}

async function orgProgramFetch(
  token: string,
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const url = `${workflowApiBase()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetch(url, {
    ...init,
    headers,
  });
}

async function orgProgramJson<T>(
  token: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await orgProgramFetch(token, path, init);
  const text = await res.text();
  if (!res.ok) {
    throw new Error(parseDetailMessage(text) || `Request failed (${res.status})`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error("Response was not JSON");
  }
}

export async function getMeOrgProgram(token: string): Promise<OrgProgramResponse> {
  return orgProgramJson<OrgProgramResponse>(token, "/api/me/org-program");
}

export async function getMeProgress(token: string): Promise<ProgressResponse> {
  return orgProgramJson<ProgressResponse>(token, "/api/me/progress");
}

const MAX_ME_CHUNK_MB = 25;
const MAX_ME_SINGLE_MB = 200;
const MAX_ME_REPORT_PARTS = 12;

export async function postMeReport(
  token: string,
  files: File | File[],
  privacyConsent: boolean,
): Promise<ReportUploadResponse> {
  const list = Array.isArray(files) ? files : [files];
  if (list.length === 0) {
    throw new Error("Choose at least one PDF.");
  }
  if (list.length > MAX_ME_REPORT_PARTS) {
    throw new Error(`At most ${MAX_ME_REPORT_PARTS} PDF parts per upload.`);
  }
  const chunkBytes = MAX_ME_CHUNK_MB * 1024 * 1024;
  const singleBytes = MAX_ME_SINGLE_MB * 1024 * 1024;
  if (list.length > 1) {
    for (const f of list) {
      if (f.size > chunkBytes) {
        throw new Error(
          `Each part must be at most ${MAX_ME_CHUNK_MB} MB (${f.name}). Or upload one PDF up to ${MAX_ME_SINGLE_MB} MB.`,
        );
      }
    }
  } else if (list[0].size > singleBytes) {
    throw new Error(`This PDF is too large (max ${MAX_ME_SINGLE_MB} MB).`);
  }
  const fd = new FormData();
  fd.append("file", list[0], list[0].name);
  for (const f of list) {
    fd.append("files", f, f.name);
  }
  fd.append("privacy_consent", privacyConsent ? "true" : "false");
  const res = await orgProgramFetch(token, "/api/me/report", {
    method: "POST",
    body: fd,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(
      `Upload failed (${res.status}): ${formatReportUploadErrorMessage(res.status, text)}`,
    );
  }
  return JSON.parse(text) as ReportUploadResponse;
}

export async function postMeAnalyze(
  token: string,
  reportId?: number | null,
): Promise<FindingsResponse> {
  const q =
    reportId != null && reportId > 0 ? `?reportId=${encodeURIComponent(String(reportId))}` : "";
  return orgProgramJson<FindingsResponse>(token, `/api/me/report/analyze${q}`, {
    method: "POST",
  });
}

export async function getMeFindings(
  token: string,
  reportId?: number | null,
): Promise<FindingsResponse> {
  const q =
    reportId != null && reportId > 0 ? `?reportId=${encodeURIComponent(String(reportId))}` : "";
  return orgProgramJson<FindingsResponse>(token, `/api/me/report/findings${q}`);
}

export async function getMeDisputeOptions(
  token: string,
  reportId?: number | null,
): Promise<DisputeOptionsResponse> {
  const q =
    reportId != null && reportId > 0 ? `?reportId=${encodeURIComponent(String(reportId))}` : "";
  return orgProgramJson<DisputeOptionsResponse>(token, `/api/me/dispute-options${q}`);
}

export async function getMeDisputeSelections(
  token: string,
  reportId?: number | null,
): Promise<{ reportId: number | null; selectedReviewClaimIds: string[]; updatedAt?: string | null }> {
  const q =
    reportId != null && reportId > 0 ? `?reportId=${encodeURIComponent(String(reportId))}` : "";
  return orgProgramJson(token, `/api/me/dispute-selections${q}`);
}

export async function postMeDisputeSelections(
  token: string,
  reportId: number,
  selectedReviewClaimIds: string[],
): Promise<{ reportId: number; selectedReviewClaimIds: string[]; updatedAt?: string | null }> {
  return orgProgramJson(token, "/api/me/dispute-selections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reportId, selectedReviewClaimIds }),
  });
}

export async function postMeGenerateLetters(
  token: string,
  reportId?: number | null,
): Promise<GenerateLettersResponse> {
  const body =
    reportId != null && reportId > 0 ? JSON.stringify({ reportId }) : JSON.stringify({});
  return orgProgramJson<GenerateLettersResponse>(token, "/api/me/generate-letters", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
  });
}

export type OrgParticipantRow = {
  userId: number;
  enrollmentId: number;
  displayName?: string | null;
  email?: string | null;
  displayLabel?: string;
  enrollmentStatus: string;
  enrolledAt?: string | null;
  activatedAt?: string | null;
  completedAt?: string | null;
  sessionId?: number | null;
  sessionCheckedInAt?: string | null;
  sessionWorkshopCompleteAt?: string | null;
  programCurrentStep?: string;
};

export type OrgWorkshopDeskResponse = {
  organizationId: number;
  session: {
    id: number;
    name: string;
    state: string;
    scheduledStartsAt?: string | null;
    startedAt?: string | null;
    endedAt?: string | null;
  };
  roster: Array<{
    userId: number;
    enrollmentId: number;
    displayName?: string | null;
    email?: string | null;
    displayLabel: string;
    programCurrentStep: string;
    programComplete: boolean;
    checkedIn: boolean;
    workshopMarkedComplete: boolean;
  }>;
  totals: {
    rosterCount: number;
    checkedInCount: number;
    workshopMarkedCompleteCount: number;
    programCompleteCount: number;
    countAtStep: Record<string, number>;
  };
  instructorFocus: {
    flowPhase: string;
    headline: string;
    sayThis: string;
    recommendedGuideStep: string;
    stuck: Array<{ userId: number; displayLabel: string; programCurrentStep: string }>;
  };
};

export type OrgProgressSummary = {
  organizationId: number;
  totalParticipants: number;
  countAtStep: Record<string, number>;
  completedAllStepsCount: number;
  percentAtStep: Record<string, number | null | undefined>;
  percentCompletedAll: number | null | undefined;
};

export type OrgSessionRow = {
  id: number;
  organizationId: number;
  name: string;
  state: string;
  scheduledStartsAt?: string | null;
  startedAt?: string | null;
  endedAt?: string | null;
};

export type OrgMemberRow = {
  id: number;
  organizationId: number;
  userId: number;
  role: string;
  status: string;
  email?: string | null;
  displayName?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export async function getOrgMembers(
  token: string,
  orgId: number,
): Promise<{ members: OrgMemberRow[] }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/members`);
}

export async function postOrgMember(
  token: string,
  orgId: number,
  body: {
    email?: string;
    userId?: number;
    role: "org_user" | "org_instructor" | "org_admin";
    enrollInProgram?: boolean;
  },
): Promise<{ membership: OrgMemberRow; enrollment?: Record<string, unknown> }> {
  const payload: Record<string, unknown> = { role: body.role };
  if (body.userId != null && body.userId > 0) payload.userId = body.userId;
  if (body.email?.trim()) payload.email = body.email.trim();
  if (body.enrollInProgram === false) payload.enrollInProgram = false;
  return orgProgramJson(token, `/api/orgs/${orgId}/members`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getOrgParticipants(
  token: string,
  orgId: number,
): Promise<{ participants: OrgParticipantRow[] }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/participants`);
}

export async function getOrgParticipantDetail(
  token: string,
  orgId: number,
  userId: number,
): Promise<Record<string, unknown>> {
  return orgProgramJson(token, `/api/orgs/${orgId}/participants/${userId}`);
}

export async function getOrgProgressSummary(
  token: string,
  orgId: number,
): Promise<OrgProgressSummary> {
  return orgProgramJson(token, `/api/orgs/${orgId}/progress`);
}

export async function getOrgOutcomesSummary(
  token: string,
  orgId: number,
): Promise<Record<string, unknown>> {
  return orgProgramJson(token, `/api/orgs/${orgId}/outcomes`);
}

export async function getOrgSessions(
  token: string,
  orgId: number,
): Promise<{ sessions: OrgSessionRow[] }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/sessions`);
}

export async function postOrgSession(
  token: string,
  orgId: number,
  name: string,
): Promise<{ session: OrgSessionRow }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
}

export async function patchOrgSession(
  token: string,
  orgId: number,
  sessionId: number,
  body: { name?: string; state?: "draft" | "scheduled" | "active" | "completed" },
): Promise<{ session: OrgSessionRow }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/sessions/${sessionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function patchOrganization(
  token: string,
  orgId: number,
  patch: Record<string, unknown>,
): Promise<{ organization: Record<string, unknown> }> {
  return orgProgramJson(token, `/api/orgs/${orgId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function postOrgEnrollmentSession(
  token: string,
  orgId: number,
  enrollmentId: number,
  sessionId: number | null,
): Promise<{ enrollment: Record<string, unknown> }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/enrollments/${enrollmentId}/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId }),
  });
}

export async function patchOrgEnrollmentWorkshop(
  token: string,
  orgId: number,
  enrollmentId: number,
  body: { checkedIn?: boolean; workshopComplete?: boolean },
): Promise<{ enrollment: Record<string, unknown> }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/enrollments/${enrollmentId}/workshop`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      checkedIn: body.checkedIn,
      workshopComplete: body.workshopComplete,
    }),
  });
}

export async function getOrgWorkshopDesk(
  token: string,
  orgId: number,
  sessionId: number,
): Promise<OrgWorkshopDeskResponse> {
  return orgProgramJson<OrgWorkshopDeskResponse>(
    token,
    `/api/orgs/${orgId}/sessions/${sessionId}/workshop-desk`,
  );
}

export type OrgProgramBillingSnapshot = {
  organizationId: number;
  paymentAccess: string;
  programAccessAllowed: boolean;
  programAccessActivatedAt?: string | null;
  onboardingStage?: string | null;
  organizationStatus?: string | null;
  usage: {
    participantSeatsActive: number;
    programEnrollments?: number;
    reportsUploaded?: number;
    disputeSelectionsSaved?: number;
    lettersGenerated?: number;
  };
  catalog: { productId: string; priceCents: number; label: string };
};

export async function getOrgProgramBilling(
  token: string,
  orgId: number,
): Promise<OrgProgramBillingSnapshot> {
  return orgProgramJson<OrgProgramBillingSnapshot>(token, `/api/orgs/${orgId}/program/billing`);
}

export async function postOrgProgramCheckout(
  token: string,
  orgId: number,
): Promise<{ checkoutUrl?: string; stripeCheckoutSessionId?: string }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/program/checkout`, { method: "POST" });
}

export async function postOrgProgramBillingReconcile(
  token: string,
  orgId: number,
  stripeCheckoutSessionId: string,
): Promise<{ ok: boolean; organization?: Record<string, unknown> }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/program/billing/reconcile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stripeCheckoutSessionId }),
  });
}

export async function postInstructorOverride(
  token: string,
  orgId: number,
  participantUserId: number,
  body: {
    action: "pause" | "resume" | "advance" | "reset";
    targetStep?: string;
    reasonSafe?: string;
  },
): Promise<{ ok: boolean }> {
  return orgProgramJson(token, `/api/orgs/${orgId}/participants/${participantUserId}/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: body.action,
      targetStep: body.targetStep,
      reasonSafe: body.reasonSafe,
    }),
  });
}
