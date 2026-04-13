import { workflowApiBase } from "@/lib/apiBase";

function connectionHint(): string {
  const base = workflowApiBase();
  if (base.startsWith("/")) {
    return "Start the workflow API (e.g. uvicorn) or set WORKFLOW_API_PROXY_TARGET in web/.env.local. If the SPA is on Vercel, set VITE_WORKFLOW_API_URL to your live API origin.";
  }
  return "Confirm VITE_WORKFLOW_API_URL is correct, the API is up, and CORS allows this site’s origin.";
}

/** User-facing message when fetch() never reaches the API (browser: “Failed to fetch”). */
export function workflowApiUnreachableMessage(): string {
  return `Could not reach the workflow API (${workflowApiBase()}). ${connectionHint()}`;
}

/**
 * Map browser “Failed to fetch” (and similar) to a clear API reachability message;
 * pass other errors through as ``Error``.
 */
export function normalizeBrowserFetchFailure(e: unknown): Error {
  const msg = e instanceof Error ? e.message : String(e);
  if (
    e instanceof TypeError &&
    (msg === "Failed to fetch" || /network|fetch|load failed/i.test(msg))
  ) {
    return new Error(workflowApiUnreachableMessage());
  }
  if (e instanceof Error) return e;
  return new Error(String(e));
}
