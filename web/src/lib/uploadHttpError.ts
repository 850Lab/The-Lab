/**
 * Report upload endpoints return FastAPI `{ detail: { messageSafe, code } }`.
 * A 413 with HTML/plain text usually means a proxy rejected the body before uvicorn saw it.
 */
export function parseWorkflowDetailMessageSafe(text: string): string | null {
  try {
    const j = JSON.parse(text) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "object" && d && "messageSafe" in d) {
      return String((d as { messageSafe: string }).messageSafe);
    }
    if (typeof d === "string") return d;
  } catch {
    /* not JSON */
  }
  return null;
}

const UPLOAD_413_PROXY_HINT =
  "If you used one PDF under the app limit and still see this, a reverse proxy or host often enforces ~25 MB before the request reaches the API. Split into several parts under 25 MB each and upload them together, or raise the platform max request body size.";

/** User-facing detail for workflow/me report multipart uploads. */
export function formatReportUploadErrorMessage(status: number, responseBody: string): string {
  const safe = parseWorkflowDetailMessageSafe(responseBody);
  if (safe) {
    if (status === 413 && safe.includes("Each PDF part must be at most")) {
      return `${safe} Or select only one PDF over 25 MB—we split it on the server.`;
    }
    return safe;
  }
  const raw = responseBody.trim();
  const snippet = raw.slice(0, 280);
  if (status === 413) {
    return [snippet, UPLOAD_413_PROXY_HINT].filter(Boolean).join(" ");
  }
  return snippet || `Request failed (HTTP ${status}).`;
}
