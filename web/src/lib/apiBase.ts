/**
 * Shared workflow API origin (customer + auth routes).
 *
 * When `VITE_WORKFLOW_API_URL` matches the page origin (e.g. same Railway host), use the
 * relative `/workflow-api` prefix so the browser stays same-origin (middleware strips it server-side).
 * That avoids broken CORS when the API is misconfigured with `Allow-Origin: *` + credentials.
 */
export function workflowApiBase(): string {
  const absolute = (
    import.meta.env.VITE_WORKFLOW_API_URL as string | undefined
  )?.trim();
  if (absolute) {
    const cleaned = absolute.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin) {
      try {
        const resolved =
          cleaned.startsWith("http://") || cleaned.startsWith("https://")
            ? cleaned
            : `https://${cleaned}`;
        const apiOrigin = new URL(resolved).origin;
        if (apiOrigin === window.location.origin) {
          return "/workflow-api";
        }
      } catch {
        /* invalid URL — fall through to cleaned */
      }
    }
    return cleaned;
  }
  const prefix = (
    import.meta.env.VITE_WORKFLOW_API_PREFIX as string | undefined
  )?.trim();
  if (prefix) return prefix.replace(/\/$/, "");
  return "/workflow-api";
}
