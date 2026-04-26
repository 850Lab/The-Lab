import type { IntakeSummaryBundle } from "@/lib/intakeTypes";
import type {
  PaymentCheckoutResponse,
  PaymentContextResponse,
  PaymentReconcileResponse,
} from "@/lib/paymentTypes";
import type { DisputeStrategyBundle } from "@/lib/strategyTypes";
import type {
  CreditCommandPlanResponse,
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
import {
  postRetailReportUploadDirect,
  ReportUploadStorageUnavailableError,
  shouldTryDirectReportUpload,
} from "@/lib/directReportUpload";
import { formatReportUploadErrorMessage } from "@/lib/uploadHttpError";
import type { EscalationLayerResponse } from "@/lib/escalationLayerTypes";
import type { WorkflowIntegrityHints } from "@/lib/integrityHintsTypes";
import type { ProgramState } from "@/lib/programStateTypes";
import type {
  ExecutionOutcomeResponse,
  ExecutionOutcomeSubmitBody,
  ExecutionStartResponse,
  ExecutionState,
} from "@/lib/executionRuntimeTypes";
import type { WorkflowEnvelope, WorkflowSyncPayload } from "@/lib/workflowTypes";
import { normalizeBrowserFetchFailure } from "@/lib/workflowNetworkErrors";

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
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch (e) {
    throw normalizeBrowserFetchFailure(e);
  }
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
  init?: RequestInit,
): Promise<WorkflowEnvelope> {
  return workflowFetchJson<WorkflowEnvelope>(
    `/api/workflows/${encodeURIComponent(workflowId)}/resume`,
    token,
    init,
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

/** Authoritative program brain: step, allowed routes, next CTA, progress, blocking. */
export async function fetchProgramState(
  token: string,
  workflowId: string,
): Promise<ProgramState> {
  const r = await workflowFetchJson<Record<string, unknown>>(
    `/api/workflows/${encodeURIComponent(workflowId)}/program-state`,
    token,
  );
  if (!r || (r as { ok?: boolean }).ok !== true) {
    const err = (r as { error?: { messageSafe?: string } } | null)?.error;
    throw new Error(
      err && typeof err.messageSafe === "string"
        ? err.messageSafe
        : "Program state is unavailable. Try again shortly.",
    );
  }
  return r as ProgramState;
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

/** After the first full cycle completes, reopen dispute selection → letters → mail for round 2+. */
export async function postBeginNextDisputeRound(
  token: string,
  workflowId: string,
): Promise<{ workflow: WorkflowEnvelope }> {
  return workflowFetchJson<{ workflow: WorkflowEnvelope }>(
    `/api/workflows/${encodeURIComponent(workflowId)}/disputes/begin-next-round`,
    token,
    { method: "POST", body: "{}" },
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

export async function fetchCreditCommandPlan(
  token: string,
  workflowId: string,
): Promise<CreditCommandPlanResponse> {
  return workflowFetchJson<CreditCommandPlanResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/credit-command-plan`,
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
  options?: { includeAiExplanation?: boolean; includeAiScript?: boolean },
): Promise<ProofContextResponse> {
  const params = new URLSearchParams();
  if (options?.includeAiExplanation === true) {
    params.set("includeAiExplanation", "true");
  }
  if (options?.includeAiScript === true) {
    params.set("includeAiScript", "true");
  }
  const q = params.toString() ? `?${params.toString()}` : "";
  return workflowFetchJson<ProofContextResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/proof/context${q}`,
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

export async function fetchEscalationLayer(
  token: string,
  workflowId: string,
): Promise<EscalationLayerResponse> {
  return workflowFetchJson<EscalationLayerResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/escalation/layer`,
    token,
  );
}

export type EscalationUxStateApiResponse = {
  workflow: WorkflowEnvelope;
  progression?: WorkflowEnvelope["progression"];
  canonicalProgression?: WorkflowEnvelope["canonicalProgression"];
};

export async function postEscalationUxState(
  token: string,
  workflowId: string,
  payload: { actionId: string; reviewed?: boolean; proceeded?: boolean },
): Promise<EscalationUxStateApiResponse> {
  return workflowFetchJson<EscalationUxStateApiResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/escalation/ux-state`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        actionId: payload.actionId,
        reviewed: payload.reviewed ?? false,
        proceeded: payload.proceeded ?? false,
      }),
    },
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

export type ReportParseIntakeStatus = {
  phase: string;
  parseJobId: string;
  parseJobStatus?: string | null;
  userSafeSummary?: string;
  nextAction?: string;
  backgroundWorkerEnabled?: boolean;
  parseErrorCode?: string;
  pendingSecondsApprox?: number;
};

export type ReportUploadResponse = {
  ok: boolean;
  reportsProcessed: number;
  fileSkips: Array<{ filename: string; reason: string }>;
  workflow: WorkflowEnvelope;
  /** Bundled with ``workflow`` on upload/finalize responses when server attaches progression payload. */
  workflowSync?: WorkflowSyncPayload;
  /** Server queued a background parse; client should poll ``/jobs/{jobId}`` until terminal. */
  processing?: boolean;
  jobId?: string;
  /** Authoritative parse-queue state from the API (upload accepted vs worker blocked vs running). */
  intakeStatus?: ReportParseIntakeStatus;
};

export type WorkflowJobPublic = {
  jobId: string;
  workflowId: string;
  jobType: string;
  status: string;
  attemptCount?: number;
  maxAttempts?: number;
  payload: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string | null;
  /** Structured code when present (failed jobs / result payload). */
  errorCode?: string | null;
  createdAt?: string;
  updatedAt?: string;
  runAt?: string | null;
};

const REPORT_PARSE_POLL_MS = 1500;
const REPORT_PARSE_TIMEOUT_MS = 45 * 60 * 1000;

/** User-facing text when ``report_upload_parse`` job fails (codes from worker / staging). */
function formatReportParseJobFailure(message: string, code: string): string {
  const c = (code || "").trim();
  const m = (message || "").trim();
  if (c === "TEMP_FILE_MISSING" || c === "PARSE_FAILED_INTAKE_ARTIFACT_MISSING") {
    return "Your PDF was received but processing could not read the saved file. This usually means the background job worker was off, the server restarted before parse ran, or storage was misconfigured. Enable WORKFLOW_JOB_WORKER_ENABLED=1 on the API, wait for DB init to finish, then try uploading again; if it repeats, check API logs.";
  }
  if (c === "FLOW_GATE") {
    return m || "This upload does not match your current program step. Refresh the page or continue from the step the app shows.";
  }
  if (c === "MISSING_STAGING_INTEGRITY" || c === "INVALID_STAGING_PAYLOAD") {
    return "Upload payload was incomplete. Try the upload again with the same file(s).";
  }
  return c ? `${m || "Report processing failed."} (${c})` : m || "Report processing failed.";
}

function _reportParseSleepMs(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }
    const t = setTimeout(() => resolve(), ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/** True when retail report polling was cancelled via ``AbortSignal``. */
export function isWorkflowReportUploadAbortError(e: unknown): boolean {
  return e instanceof DOMException && e.name === "AbortError";
}

/**
 * Wait for ``report_upload_parse`` job to finish, then return the same shape as a synchronous
 * upload response (refreshed ``workflow`` from resume after parse completes).
 */
export async function pollReportUploadParseJob(
  token: string,
  workflowId: string,
  jobId: string,
  options?: { signal?: AbortSignal },
): Promise<ReportUploadResponse> {
  const signal = options?.signal;
  const terminal = new Set(["completed", "failed"]);
  const start = Date.now();
  while (Date.now() - start < REPORT_PARSE_TIMEOUT_MS) {
    if (signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }
    const j = await workflowFetchJson<{
      ok: boolean;
      job: WorkflowJobPublic;
      intakeStatus?: ReportParseIntakeStatus;
    }>(
      `/api/workflows/${encodeURIComponent(workflowId)}/jobs/${encodeURIComponent(jobId)}`,
      token,
      { signal },
    );
    const st = j.job.status;
    if (terminal.has(st)) {
      if (st === "failed") {
        const msg =
          typeof j.job.error === "string" && j.job.error.trim()
            ? j.job.error.trim()
            : "Report processing failed.";
        const resFail = j.job.result;
        const codeFromResult =
          resFail && typeof resFail === "object" && "errorCode" in resFail
            ? String((resFail as { errorCode?: string }).errorCode ?? "").trim()
            : "";
        const code = (j.job.errorCode && String(j.job.errorCode).trim()) || codeFromResult;
        throw new Error(formatReportParseJobFailure(msg, code));
      }
      const res = j.job.result;
      const ok = Boolean(res && typeof res === "object" && (res as { ok?: boolean }).ok);
      const reportsProcessed = Number(
        (res as { reportsProcessed?: number } | null)?.reportsProcessed ?? 0,
      );
      const rawSkips = (res as { fileSkips?: unknown } | null)?.fileSkips;
      const fileSkips = Array.isArray(rawSkips)
        ? (rawSkips as Array<{ filename: string; reason: string }>)
        : [];
      const workflow = await fetchWorkflowResume(token, workflowId, { signal });
      return {
        ok,
        reportsProcessed,
        fileSkips,
        workflow,
        intakeStatus: j.intakeStatus,
      };
    }
    await _reportParseSleepMs(REPORT_PARSE_POLL_MS, signal);
  }
  throw new Error(
    "Report processing is taking longer than expected. Try a smaller PDF or upload again. If uploads never finish, the API background worker may be disabled — set WORKFLOW_JOB_WORKER_ENABLED=1 (default) and confirm the service logs show database init completed.",
  );
}

/** Manual multi-part uploads: each piece stays under this (server merges). */
const MAX_REPORT_CHUNK_MB = 25;
/** One full bureau PDF; larger files are split by page server-side then merged for parsing. */
const MAX_SINGLE_REPORT_MB = 200;
const MAX_REPORT_PARTS = 12;

/** Legacy multipart → ``POST .../reports/upload`` (same pipeline as Streamlit). */
export async function postReportUploadMultipart(
  token: string,
  workflowId: string,
  files: File | File[],
  privacyConsent: boolean,
): Promise<ReportUploadResponse> {
  const list = Array.isArray(files) ? files : [files];
  if (list.length === 0) {
    throw new Error("Choose at least one PDF.");
  }
  if (list.length > MAX_REPORT_PARTS) {
    throw new Error(`At most ${MAX_REPORT_PARTS} PDF parts per upload.`);
  }
  const chunkBytes = MAX_REPORT_CHUNK_MB * 1024 * 1024;
  const singleBytes = MAX_SINGLE_REPORT_MB * 1024 * 1024;
  if (list.length > 1) {
    for (const f of list) {
      if (f.size > chunkBytes) {
        throw new Error(
          `Each part must be at most ${MAX_REPORT_CHUNK_MB} MB (${f.name}). Or upload one large PDF (up to ${MAX_SINGLE_REPORT_MB} MB) and we split it automatically.`,
        );
      }
    }
  } else if (list[0].size > singleBytes) {
    throw new Error(`This PDF is too large (max ${MAX_SINGLE_REPORT_MB} MB).`);
  }
  const fd = new FormData();
  // Primary field name expected by older APIs and some proxies; keep `files` for multi-part merge.
  fd.append("file", list[0], list[0].name);
  for (const f of list) {
    fd.append("files", f, f.name);
  }
  fd.append("privacy_consent", privacyConsent ? "true" : "false");
  const url = `${apiBase()}/api/workflows/${encodeURIComponent(workflowId)}/reports/upload`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: fd,
    });
  } catch (e) {
    throw normalizeBrowserFetchFailure(e);
  }
  const text = await res.text();
  if (!res.ok) {
    throw new Error(
      `Upload failed (${res.status}): ${formatReportUploadErrorMessage(res.status, text)}`,
    );
  }
  return JSON.parse(text) as ReportUploadResponse;
}

/**
 * Single-file: presigned session → PUT → finalize when enabled; otherwise or on storage-unavailable,
 * multipart ``postReportUploadMultipart``. Multi-part uploads always use multipart.
 */
export async function postReportUpload(
  token: string,
  workflowId: string,
  files: File | File[],
  privacyConsent: boolean,
): Promise<ReportUploadResponse> {
  const list = Array.isArray(files) ? files : [files];
  if (list.length === 0) {
    throw new Error("Choose at least one PDF.");
  }
  if (list.length > MAX_REPORT_PARTS) {
    throw new Error(`At most ${MAX_REPORT_PARTS} PDF parts per upload.`);
  }
  const chunkBytes = MAX_REPORT_CHUNK_MB * 1024 * 1024;
  const singleBytes = MAX_SINGLE_REPORT_MB * 1024 * 1024;
  if (list.length > 1) {
    for (const f of list) {
      if (f.size > chunkBytes) {
        throw new Error(
          `Each part must be at most ${MAX_REPORT_CHUNK_MB} MB (${f.name}). Or upload one large PDF (up to ${MAX_SINGLE_REPORT_MB} MB) and we split it automatically.`,
        );
      }
    }
  } else if (list[0].size > singleBytes) {
    throw new Error(`This PDF is too large (max ${MAX_SINGLE_REPORT_MB} MB).`);
  }

  if (shouldTryDirectReportUpload(list.length)) {
    try {
      return await postRetailReportUploadDirect(token, workflowId, list[0]!);
    } catch (e) {
      if (e instanceof ReportUploadStorageUnavailableError) {
        return postReportUploadMultipart(token, workflowId, files, privacyConsent);
      }
      throw e;
    }
  }
  return postReportUploadMultipart(token, workflowId, files, privacyConsent);
}

// --- Guided execution runtime (services.execution_runtime) ---

export async function startExecutionSession(
  token: string,
  workflowId: string,
): Promise<ExecutionStartResponse> {
  return workflowFetchJson<ExecutionStartResponse>(
    `/api/workflows/${encodeURIComponent(workflowId)}/execution/start`,
    token,
    { method: "POST", body: "{}" },
  );
}

export async function fetchExecutionState(
  token: string,
  query: { workflowId: string } | { runId: string },
): Promise<ExecutionState> {
  if ("runId" in query) {
    const j = await workflowFetchJson<{ executionState: ExecutionState }>(
      `/api/execution/runs/${encodeURIComponent(query.runId)}/state`,
      token,
    );
    return j.executionState;
  }
  const j = await workflowFetchJson<{ executionState: ExecutionState }>(
    `/api/workflows/${encodeURIComponent(query.workflowId)}/execution/state`,
    token,
  );
  return j.executionState;
}

export async function submitExecutionOutcome(
  token: string,
  runId: string,
  body: ExecutionOutcomeSubmitBody,
): Promise<ExecutionOutcomeResponse> {
  return workflowFetchJson<ExecutionOutcomeResponse>(
    `/api/execution/runs/${encodeURIComponent(runId)}/outcome`,
    token,
    {
      method: "POST",
      body: JSON.stringify({
        blockId: body.blockId,
        outcomeKey: body.outcomeKey,
        notes: body.notes ?? "",
        externalFlags: body.externalFlags ?? {},
        source: body.source ?? "user_reported",
      }),
    },
  );
}
