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

async function authFetchJson<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${workflowApiBase()}${path.startsWith("/") ? path : `/${path}`}`;
  const res = await fetch(url, init);
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
