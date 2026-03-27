/** Shared workflow API origin (customer + auth routes). */
export function workflowApiBase(): string {
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
