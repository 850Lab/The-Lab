/**
 * Path 2: presigned session → browser PUT to object storage → finalize → same parse job as multipart.
 */

import { workflowApiBase } from "@/lib/apiBase";
import type { ReportUploadResponse as OrgReportUploadResponse } from "@/lib/orgProgramTypes";
import { formatReportUploadErrorMessage } from "@/lib/uploadHttpError";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";

function apiBase(): string {
  return workflowApiBase();
}

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

/** Thrown when session or finalize returns 503 so callers can fall back to multipart upload. */
export class ReportUploadStorageUnavailableError extends Error {
  override readonly name = "ReportUploadStorageUnavailableError";
}

export type DirectReportUploadSessionResponse = {
  ok: boolean;
  uploadId: string;
  uploadUrl: string;
  objectKey: string;
  constraints?: {
    contentType?: string;
    maxSingleFileBytes?: number;
  };
  presignedExpiresIn?: number;
  sessionExpiresAt?: string;
};

/** SHA-256 hex digest of buffer (SubtleCrypto). */
export async function sha256HexOfArrayBuffer(buf: ArrayBuffer): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", buf);
  const bytes = new Uint8Array(hash);
  let hex = "";
  for (let i = 0; i < bytes.length; i++) {
    hex += bytes[i]!.toString(16).padStart(2, "0");
  }
  return hex;
}

function isStorageUnavailableResponse(status: number, text: string): boolean {
  if (status !== 503) return false;
  try {
    const j = JSON.parse(text) as { detail?: { code?: string } };
    return j.detail?.code === "REPORT_UPLOAD_STORAGE_UNAVAILABLE";
  } catch {
    return true;
  }
}

function throwStorageUnavailableIfApplicable(
  status: number,
  text: string,
  fallbackMsg: string,
): void {
  if (isStorageUnavailableResponse(status, text)) {
    throw new ReportUploadStorageUnavailableError(
      parseDetailMessage(text) || fallbackMsg,
    );
  }
}

/** Same shape as ``ReportUploadResponse`` in ``workflowApi`` (avoid circular import). */
export type RetailReportUploadDirectResult = {
  ok: boolean;
  reportsProcessed: number;
  fileSkips: Array<{ filename: string; reason: string }>;
  workflow: WorkflowEnvelope;
  processing?: boolean;
  jobId?: string;
};

/** Retail: session → PUT → finalize → shape expected by UploadStep + polling. */
export async function postRetailReportUploadDirect(
  token: string,
  workflowId: string,
  file: File,
): Promise<RetailReportUploadDirectResult> {
  const wid = encodeURIComponent(workflowId);
  const sessionUrl = `${apiBase()}/api/workflows/${wid}/report-upload/session`;
  const sessionRes = await fetch(sessionUrl, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  const sessionText = await sessionRes.text();
  if (!sessionRes.ok) {
    throwStorageUnavailableIfApplicable(
      sessionRes.status,
      sessionText,
      "Direct upload is not available.",
    );
    throw new Error(
      `Could not start upload (${sessionRes.status}): ${formatReportUploadErrorMessage(
        sessionRes.status,
        sessionText,
      )}`,
    );
  }
  const session = JSON.parse(sessionText) as DirectReportUploadSessionResponse;
  if (!session.uploadUrl || !session.uploadId) {
    throw new Error("Invalid session response from server.");
  }

  const contentType =
    session.constraints?.contentType?.trim() || "application/pdf";

  const buf = await file.arrayBuffer();
  const byteSize = buf.byteLength;

  const putRes = await fetch(session.uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: buf,
  });
  if (!putRes.ok) {
    const t = await putRes.text().catch(() => "");
    throw new Error(
      `Could not upload file to storage (${putRes.status}): ${t.slice(0, 280) || putRes.statusText}`,
    );
  }

  const sha256Hex = await sha256HexOfArrayBuffer(buf);

  const finUrl = `${apiBase()}/api/workflows/${wid}/report-upload/finalize`;
  const finRes = await fetch(finUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      uploadId: session.uploadId,
      byteSize,
      sha256Hex,
    }),
  });
  const finText = await finRes.text();
  if (!finRes.ok) {
    throwStorageUnavailableIfApplicable(
      finRes.status,
      finText,
      "Could not finalize direct upload.",
    );
    throw new Error(
      `Could not finalize upload (${finRes.status}): ${formatReportUploadErrorMessage(
        finRes.status,
        finText,
      )}`,
    );
  }
  const fin = JSON.parse(finText) as {
    ok?: boolean;
    jobId?: string;
    processing?: boolean;
    workflow?: WorkflowEnvelope;
  };

  const workflow = fin.workflow as WorkflowEnvelope | undefined;
  if (!workflow) {
    throw new Error("Finalize response missing workflow envelope.");
  }

  return {
    ok: Boolean(fin.ok),
    processing: Boolean(fin.processing),
    jobId: fin.jobId,
    reportsProcessed: 0,
    fileSkips: [],
    workflow,
  };
}

/** Org: session → PUT → finalize → same shape as multipart ``postMeReport``. */
export async function postOrgReportUploadDirect(
  token: string,
  file: File,
): Promise<OrgReportUploadResponse> {
  const sessionUrl = `${apiBase()}/api/me/report-upload/session`;
  const sessionRes = await fetch(sessionUrl, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  const sessionText = await sessionRes.text();
  if (!sessionRes.ok) {
    throwStorageUnavailableIfApplicable(
      sessionRes.status,
      sessionText,
      "Direct upload is not available.",
    );
    throw new Error(
      `Could not start upload (${sessionRes.status}): ${parseDetailMessage(sessionText)}`,
    );
  }
  const session = JSON.parse(sessionText) as DirectReportUploadSessionResponse;
  if (!session.uploadUrl || !session.uploadId) {
    throw new Error("Invalid session response from server.");
  }

  const contentType =
    session.constraints?.contentType?.trim() || "application/pdf";

  const buf = await file.arrayBuffer();
  const byteSize = buf.byteLength;

  const putRes = await fetch(session.uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: buf,
  });
  if (!putRes.ok) {
    const t = await putRes.text().catch(() => "");
    throw new Error(
      `Could not upload file to storage (${putRes.status}): ${t.slice(0, 280) || putRes.statusText}`,
    );
  }

  const sha256Hex = await sha256HexOfArrayBuffer(buf);

  const finUrl = `${apiBase()}/api/me/report-upload/finalize`;
  const finRes = await fetch(finUrl, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      uploadId: session.uploadId,
      byteSize,
      sha256Hex,
    }),
  });
  const finText = await finRes.text();
  if (!finRes.ok) {
    throwStorageUnavailableIfApplicable(
      finRes.status,
      finText,
      "Could not finalize direct upload.",
    );
    throw new Error(
      `Could not finalize upload (${finRes.status}): ${parseDetailMessage(finText)}`,
    );
  }
  return JSON.parse(finText) as OrgReportUploadResponse;
}

/** Single-file direct path when env allows and not forced to legacy-only. */
export function shouldTryDirectReportUpload(fileCount: number): boolean {
  if (import.meta.env.VITE_USE_DIRECT_REPORT_UPLOAD === "0") {
    return false;
  }
  return fileCount === 1;
}
