/**
 * Resolve in-app path from ?next= (open-redirect safe) or router state.
 */
export function safeAppPath(raw: string | null | undefined): string | null {
  if (raw == null || raw === "") return null;
  let p: string;
  try {
    p = decodeURIComponent(raw.trim());
  } catch {
    return null;
  }
  if (!p.startsWith("/") || p.startsWith("//")) return null;
  if (p.includes("://")) return null;
  const noHash = p.split("#")[0] ?? p;
  return noHash || null;
}

export function postAuthTargetFromSearchAndState(
  search: string,
  stateFrom: string | undefined,
  excludePath: string,
): string {
  const q = new URLSearchParams(search);
  const fromNext = safeAppPath(q.get("next"));
  if (fromNext && fromNext !== excludePath) return fromNext;
  const fromState = safeAppPath(stateFrom);
  if (fromState && fromState !== excludePath) return fromState;
  return "/";
}
