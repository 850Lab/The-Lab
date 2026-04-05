import { workflowApiBase } from "@/lib/apiBase";
import type { AuthLoginResponse, AuthMeResponse, AuthUser } from "@/lib/authTypes";

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

function authNetworkHelp(base: string): string {
  const isRelative = base.startsWith("/");
  if (isRelative) {
    return `Start the workflow API (e.g. python -m uvicorn api.workflow_app:app --host 127.0.0.1 --port 5000) or set WORKFLOW_API_PROXY_TARGET in web/.env.local if it uses another port. Then restart npm run dev.`;
  }
  return `Check VITE_WORKFLOW_API_URL in web/.env.local — the browser must be able to reach that host (CORS is enabled on the API). For local dev, remove VITE_WORKFLOW_API_URL so requests use the Vite proxy at /workflow-api.`;
}

async function authFetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const base = workflowApiBase();
  const url = `${base}${path.startsWith("/") ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    if (
      e instanceof TypeError &&
      (msg === "Failed to fetch" || /network|fetch|load failed/i.test(msg))
    ) {
      throw new Error(
        `Could not reach the workflow API (${base}). ${authNetworkHelp(base)}`,
      );
    }
    throw e;
  }
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Auth API ${res.status}: ${parseDetailMessage(text)}`);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    throw new Error("Auth API: response was not JSON");
  }
}

function mapUser(raw: Record<string, unknown>): AuthUser {
  return {
    id: Number(raw.id),
    email: String(raw.email ?? ""),
    displayName:
      raw.displayName == null ? null : String(raw.displayName),
    role: String(raw.role ?? "consumer"),
    tier: String(raw.tier ?? "free"),
    emailVerified: Boolean(raw.emailVerified),
  };
}

export async function authLogin(
  email: string,
  password: string,
): Promise<{ token: string; user: AuthUser }> {
  const j = await authFetchJson<AuthLoginResponse & { user: Record<string, unknown> }>(
    "/api/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
  );
  return { token: j.token, user: mapUser(j.user as Record<string, unknown>) };
}

export async function authSignup(
  email: string,
  password: string,
  displayName: string,
): Promise<{ token: string; user: AuthUser }> {
  const j = await authFetchJson<AuthLoginResponse & { user: Record<string, unknown> }>(
    "/api/auth/signup",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name: displayName }),
    },
  );
  return { token: j.token, user: mapUser(j.user as Record<string, unknown>) };
}

export async function authMe(token: string): Promise<AuthUser> {
  const j = await authFetchJson<AuthMeResponse & { user: Record<string, unknown> }>(
    "/api/auth/me",
    { headers: { Authorization: `Bearer ${token}` } },
  );
  return mapUser(j.user as Record<string, unknown>);
}

export async function authLogout(token: string): Promise<void> {
  await authFetchJson<{ ok: boolean }>("/api/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function authVerifyEmail(
  token: string,
  code: string,
): Promise<void> {
  await authFetchJson<{ ok: boolean }>("/api/auth/verify-email", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ code }),
  });
}

export async function authResendVerification(token: string): Promise<void> {
  await authFetchJson<{ ok: boolean }>("/api/auth/resend-verification", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function authForgotPassword(email: string): Promise<void> {
  await authFetchJson<{ ok: boolean }>("/api/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function authResetPassword(
  email: string,
  code: string,
  password: string,
): Promise<void> {
  await authFetchJson<{ ok: boolean }>("/api/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, code, password }),
  });
}
