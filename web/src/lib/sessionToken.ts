const STORAGE_KEY = "850lab_session_token";

function readLocal(): string {
  try {
    return localStorage.getItem(STORAGE_KEY)?.trim() ?? "";
  } catch {
    return "";
  }
}

function readSession(): string {
  try {
    return sessionStorage.getItem(STORAGE_KEY)?.trim() ?? "";
  } catch {
    return "";
  }
}

/**
 * Session bearer for workflow API (`Authorization: Bearer …`), same DB token as Streamlit.
 * Priority: VITE_SESSION_BEARER_TOKEN → localStorage (standalone React) → sessionStorage (legacy handoff)
 * → auth_token cookie (Streamlit).
 */
export function readSessionBearerToken(): string {
  const env = (import.meta.env.VITE_SESSION_BEARER_TOKEN as string | undefined)?.trim();
  if (env) return env;
  const fromLocal = readLocal();
  if (fromLocal) return fromLocal;
  const fromSession = readSession();
  if (fromSession) return fromSession;
  if (typeof document !== "undefined") {
    const m = document.cookie.match(/(?:^|;\s*)auth_token=([^;]+)/);
    if (m?.[1]) {
      try {
        return decodeURIComponent(m[1].trim());
      } catch {
        return m[1].trim();
      }
    }
  }
  return "";
}

/** Persist customer session (survives refresh and return from Stripe checkout). */
export function setCustomerSessionToken(token: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, token.trim());
  } catch {
    /* quota / private mode */
  }
  try {
    sessionStorage.setItem(STORAGE_KEY, token.trim());
  } catch {
    /* ignore */
  }
}

/** Persist token from `?auth_token=` (e.g. legacy Streamlit handoff). */
export function persistSessionTokenFromSearch(search: string): void {
  try {
    const q = new URLSearchParams(search);
    const t = q.get("auth_token")?.trim();
    if (t) setCustomerSessionToken(t);
  } catch {
    /* ignore */
  }
}

export function clearStoredSessionToken(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}
