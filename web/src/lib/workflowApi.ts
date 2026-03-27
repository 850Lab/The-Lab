import type { IntakeSummaryBundle } from "@/lib/intakeTypes";
import type {
  PaymentCheckoutResponse,
  PaymentContextResponse,
  PaymentReconcileResponse,
} from "@/lib/paymentTypes";
import type { DisputeStrategyBundle } from "@/lib/strategyTypes";
import type {
  LettersContextResponse,
  LettersGenerateResponse,
} from "@/lib/letterTypes";
import type {
  MailContextResponse,
  MailSendBureauPayload,
  MailSendBureauResponse,
} from "@/lib/mailTypes";
import type { ProofContextResponse } from "@/lib/proofTypes";
import type {
  ResponseIntakeSubmitResponse,
  WorkflowResponseMetricsResponse,
  WorkflowResponsesListResponse,
} from "@/lib/responseTypes";
import type { TrackingContextResponse } from "@/lib/trackingTypes";
import { workflowApiBase } from "@/lib/apiBase";
import type { WorkflowIntegrityHints } from "@/lib/integrityHintsTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";

function apiBase(): string {
  return workflowApiBase();
}

async function workflowFetchJson<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${apiBase()}${path.startsWith("/") ? path : `/${path}`}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (init?.body != null && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(url, { ...init, headers });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Workflow API ${res.status}: ${text.slice(0, 500)}`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error("Workflow API: response was not JSON");
  }
}

function workflowErrorMessageFromBody(text: string, fallback: string): string {
  try {
    const j = JSON.parse(text) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "object" && d && "messageSafe" in d) {
      return String((d as { messageSafe: string }).messageSafe);
    }
    if (typeof d === "string") return d;
  } catch {
    /* keep fallback */
  }
  return text.slice(0, 500) || fallback;
}

export async function fetchActiveWorkflowId(
  token: string,
): Promise<string | null> {
  const j = await workflowFetchJson<{ workflowId: string | null }>(
    "/api/workflows/active",
    token,
  );
  return j.workflowId ?? null;
}

export async function fetchWorkflowResume(
  token: string,
  workflowId: string,
): Promise<WorkflowEnvelope> {
  return workflowFetchJson<WorkflowEnvelope>(
    `/api/workflows/${encodeURIComponent(workflowId)}/resume`,
    token,
  );
}

export async function fetchWorkflowIntegrityHints(
  token: string,
  workflowId: string,
): Promise<WorkflowIntegrityHints> {
  return workflowFetchJson<WorkflowIntegrityHints>(
    `/api/workflows/${encodeURIComponent(workflowId)}/integrity-hints`,
    token,
  );
}

export async function fetchWorkflowState(
  token: string,
  workflowId: string,
): Promise<WorkflowEnvelope> {
  return workflowFetchJson<WorkflowEnvelope>(
    `/api/workflows/${encodeURIComponent(workflowId)}/state`,
    token,
  );
}

/** Parsed reports + compressed review claims (same extract/compress path as Streamlit). */
export async function fetchIntakeSummary(
  token: string,
  workflowId: string,
): Promise<IntakeSummaryBundle> {
  return workflowFetchJson<IntakeSummaryBundle>(
    `/api/workflows/${encodeURIComponent(workflowId)}/intake/summary`,
    token,
  );
}

export type IntakeAcknowledgeReviewResponse = {
  workflow: WorkflowEnvelope;
};

/** Completes workflow step ``review_claims`` (trusted hook, same as Streamlit). */
export async function postAcknowledgeReview(
  token: string,
  workflowId: string,
  body?: { item_count?: number },
): Promise<IntakeAcknowledgeReviewResponse> {
  return workflowFetchJson<IntakeAcknowledgeReviewResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/intake/acknowledge-review`,
    token,
    { method: "POST", body: JSON.stringify(body ?? {}) },
  );
}

export async function fetchDisputeStrategy(
  token: string,
  workflowId: string,
): Promise<DisputeStrategyBundle> {
  return workflowFetchJson<DisputeStrategyBundle>(
    `/api/workflows/${encodeURIComponent(workflowId)}/disputes/strategy`,
    token,
  );
}

export async function putDisputeSelectionDraft(
  token: string,
  workflowId: string,
  draft_selected_review_claim_ids: string[],
): Promise<{ workflow: WorkflowEnvelope }> {
  return workflowFetchJson<{ workflow: WorkflowEnvelope }>(
    `/api/workflows/${encodeURIComponent(workflowId)}/disputes/selection`,
    token,
    {
      method: "PUT",
      body: JSON.stringify({ draft_selected_review_claim_ids }),
    },
  );
}

export async function postDisputeSelectionConfirm(
  token: string,
  workflowId: string,
  selected_review_claim_ids: string[],
): Promise<{ workflow: WorkflowEnvelope }> {
  return workflowFetchJson<{ workflow: WorkflowEnvelope }>(
    `/api/workflows/${encodeURIComponent(workflowId)}/disputes/selection/confirm`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ selected_review_claim_ids }),
    },
  );
}

export async function fetchPaymentContext(
  token: string,
  workflowId: string,
): Promise<PaymentContextResponse> {
  return workflowFetchJson<PaymentContextResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/payment/context`,
    token,
  );
}

export async function postPaymentCheckout(
  token: string,
  workflowId: string,
  product_id: string,
): Promise<PaymentCheckoutResponse> {
  return workflowFetchJson<PaymentCheckoutResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/payment/checkout`,
    token,
    { method: "POST", body: JSON.stringify({ product_id }) },
  );
}

export async function postPaymentReconcile(
  token: string,
  workflowId: string,
  stripe_checkout_session_id: string,
): Promise<PaymentReconcileResponse> {
  return workflowFetchJson<PaymentReconcileResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/payment/reconcile`,
    token,
    {
      method: "POST",
      body: JSON.stringify({ stripe_checkout_session_id }),
    },
  );
}

export async function postPaymentContinueWithCredits(
  token: string,
  workflowId: string,
): Promise<{ workflow: WorkflowEnvelope }> {
  return workflowFetchJson<{ workflow: WorkflowEnvelope }>(
    `/api/workflows/${encodeURIComponent(workflowId)}/payment/continue-with-credits`,
    token,
    { method: "POST", body: "{}" },
  );
}

/** Letter rows + workflow UI flags for the customer /letters step. */
export async function fetchLettersContext(
  token: string,
  workflowId: string,
): Promise<LettersContextResponse> {
  return workflowFetchJson<LettersContextResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/letters/context`,
    token,
  );
}

/**
 * Runs ``process_dispute_pipeline`` with DB-backed context (same as Streamlit).
 * Completes workflow step ``letter_generation`` on success.
 */
export async function postLettersGenerate(
  token: string,
  workflowId: string,
): Promise<LettersGenerateResponse> {
  const url = `${apiBase()}/api/workflows/${encodeURIComponent(workflowId)}/letters/generate`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: "{}",
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(
      `Workflow API ${res.status}: ${workflowErrorMessageFromBody(text, "Letter generation failed")}`,
    );
  }
  try {
    return JSON.parse(text) as LettersGenerateResponse;
  } catch {
    throw new Error("Workflow API: letter generation response was not JSON");
  }
}

export async function fetchLetterContent(
  token: string,
  workflowId: string,
  letterId: number,
): Promise<{ letterText: string }> {
  return workflowFetchJson<{ letterText: string }>(
    `/api/workflows/${encodeURIComponent(workflowId)}/letters/${letterId}/content`,
    token,
  );
}

/** Plain-text bundle of the user’s letters (deduped per report + bureau). */
export async function fetchLettersBundleTxt(
  token: string,
  workflowId: string,
): Promise<string> {
  const url = `${apiBase()}/api/workflows/${encodeURIComponent(workflowId)}/letters/bundle.txt`;
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(
      `Workflow API ${res.status}: ${workflowErrorMessageFromBody(text, "Download failed")}`,
    );
  }
  return text;
}

export async function fetchProofContext(
  token: string,
  workflowId: string,
): Promise<ProofContextResponse> {
  return workflowFetchJson<ProofContextResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/proof/context`,
    token,
  );
}

export async function postProofUpload(
  token: string,
  workflowId: string,
  docType: "government_id" | "address_proof",
  file: File,
): Promise<ProofContextResponse> {
  const fd = new FormData();
  fd.append("doc_type", docType);
  fd.append("file", file);
  const url = `${apiBase()}/api/workflows/${encodeURIComponent(workflowId)}/proof/upload`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(
      `Workflow API ${res.status}: ${workflowErrorMessageFromBody(text, "Upload failed")}`,
    );
  }
  return JSON.parse(text) as ProofContextResponse;
}

export async function postProofSignature(
  token: string,
  workflowId: string,
  pngBlob: Blob,
): Promise<ProofContextResponse> {
  const fd = new FormData();
  fd.append("file", pngBlob, "signature.png");
  const url = `${apiBase()}/api/workflows/${encodeURIComponent(workflowId)}/proof/signature`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(
      `Workflow API ${res.status}: ${workflowErrorMessageFromBody(text, "Could not save signature")}`,
    );
  }
  return JSON.parse(text) as ProofContextResponse;
}

export async function fetchMailContext(
  token: string,
  workflowId: string,
): Promise<MailContextResponse> {
  return workflowFetchJson<MailContextResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/mail/context`,
    token,
  );
}

export async function postMailSendBureau(
  token: string,
  workflowId: string,
  body: MailSendBureauPayload,
): Promise<MailSendBureauResponse> {
  return workflowFetchJson<MailSendBureauResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/mail/send-bureau`,
    token,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}

/** Lob send rows per bureau, mail-gate metadata, workflow flags, ``build_home_summary`` hints (DB truth; no live Lob polling). */
export async function fetchTrackingContext(
  token: string,
  workflowId: string,
): Promise<TrackingContextResponse> {
  return workflowFetchJson<TrackingContextResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/tracking/context`,
    token,
  );
}

export async function fetchWorkflowResponses(
  token: string,
  workflowId: string,
  limit = 30,
): Promise<WorkflowResponsesListResponse> {
  const q = limit !== 30 ? `?limit=${encodeURIComponent(String(limit))}` : "";
  return workflowFetchJson<WorkflowResponsesListResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/responses${q}`,
    token,
  );
}

/** Workflow-scoped response intake metrics from persisted intake rows (with resume envelope). */
export async function fetchWorkflowResponseMetrics(
  token: string,
  workflowId: string,
): Promise<WorkflowResponseMetricsResponse> {
  return workflowFetchJson<WorkflowResponseMetricsResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/responses/metrics`,
    token,
  );
}

export type ResponseIntakeBody = {
  source_type?: string;
  response_channel?: string;
  parsed_summary: Record<string, unknown>;
  storage_ref?: string | null;
  linked_mailing_id?: number | null;
  linked_letter_id?: number | null;
};

/** Creates intake row, runs rule-based classification + escalation recommendation (same as Streamlit/internal). */
export async function postResponseIntake(
  token: string,
  workflowId: string,
  body: ResponseIntakeBody,
): Promise<ResponseIntakeSubmitResponse> {
  return workflowFetchJson<ResponseIntakeSubmitResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/responses/intake`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        source_type: body.source_type ?? "bureau",
        response_channel: body.response_channel ?? "manual_entry",
        parsed_summary: body.parsed_summary,
        storage_ref: body.storage_ref ?? undefined,
        linked_mailing_id: body.linked_mailing_id ?? undefined,
        linked_letter_id: body.linked_letter_id ?? undefined,
      }),
    },
  );
}

export type CustomerUxEventBody = {
  event_name: string;
  step_id?: string;
  status?: string;
  metadata?: Record<string, unknown>;
};

/** Lightweight UX milestones (logged as workflow audit lines; user from session). */
export async function postCustomerUxEvent(
  token: string,
  workflowId: string,
  body: CustomerUxEventBody,
): Promise<{ ok: boolean }> {
  return workflowFetchJson<{ ok: boolean }>(
    `/api/workflows/${encodeURIComponent(workflowId)}/events/customer-ux`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        event_name: body.event_name,
        step_id: body.step_id ?? "track",
        status: body.status ?? "ok",
        metadata: body.metadata ?? {},
      }),
    },
  );
}

export async function postWorkflowInit(
  token: string,
  body?: { workflow_type?: string; metadata?: Record<string, unknown> },
): Promise<WorkflowEnvelope> {
  return workflowFetchJson<WorkflowEnvelope>("/api/workflows/init", token, {
    method: "POST",
    body: JSON.stringify(body ?? {}),
  });
}

export async function postStepStart(
  token: string,
  workflowId: string,
  stepId: string,
): Promise<WorkflowEnvelope> {
  return workflowFetchJson<WorkflowEnvelope>(
    `/api/workflows/${encodeURIComponent(workflowId)}/steps/${encodeURIComponent(stepId)}/start`,
    token,
    { method: "POST", body: "{}" },
  );
}

export type ReportUploadResponse = {
  ok: boolean;
  reportsProcessed: number;
  fileSkips: Array<{ filename: string; reason: string }>;
  workflow: WorkflowEnvelope;
};

/** Multipart upload → same ``report_pipeline`` as Streamlit; completes upload + parse_analyze hooks. */
export async function postReportUpload(
  token: string,
  workflowId: string,
  file: File,
  privacyConsent: boolean,
): Promise<ReportUploadResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("privacy_consent", privacyConsent ? "true" : "false");
  const url = `${apiBase()}/api/workflows/${encodeURIComponent(workflowId)}/reports/upload`;
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  const text = await res.text();
  if (!res.ok) {
    let detail = text.slice(0, 500);
    try {
      const j = JSON.parse(text) as { detail?: unknown };
      if (typeof j.detail === "object" && j.detail && "messageSafe" in j.detail) {
        detail = String((j.detail as { messageSafe: string }).messageSafe);
      } else if (typeof j.detail === "string") {
        detail = j.detail;
      }
    } catch {
      /* keep slice */
    }
    throw new Error(`Upload failed (${res.status}): ${detail}`);
  }
  return JSON.parse(text) as ReportUploadResponse;
}
