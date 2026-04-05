import { workflowApiBase } from "@/lib/apiBase";
import { readSessionBearerToken } from "@/lib/sessionToken";
import type { GtmVerification } from "@/lib/launchPreviewManifest";

export type ProbeState =
  | { status: "idle" }
  | { status: "checking" }
  | { status: "pass"; detail: string }
  | { status: "fail"; detail: string }
  | { status: "skipped"; detail: string };

export async function runVerification(
  verification: GtmVerification,
): Promise<ProbeState> {
  if (verification.mode === "declared") {
    return {
      status: "pass",
      detail: verification.note
        ? `${verification.location} — ${verification.note}`
        : verification.location,
    };
  }

  const base = workflowApiBase();
  const url = `${base}${verification.path.startsWith("/") ? verification.path : `/${verification.path}`}`;
  const token =
    verification.bearer === "optional" || verification.bearer === "required"
      ? readSessionBearerToken()
      : undefined;

  if (verification.bearer === "required" && !token) {
    return {
      status: "skipped",
      detail: "Sign in (customer session) to verify this call.",
    };
  }

  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    const res = await fetch(url, {
      method: "GET",
      headers,
      credentials: "omit",
    });
    const ok2xx = res.status >= 200 && res.status < 300;
    const ok401 = res.status === 401;

    let pass = false;
    if (verification.okIf === "2xx") pass = ok2xx;
    else if (verification.okIf === "401") pass = ok401;
    else if (verification.okIf === "2xx_or_401") pass = ok2xx || ok401;
    else if (verification.okIf === "any_http") pass = Number.isFinite(res.status);

    if (pass) {
      return { status: "pass", detail: `HTTP ${res.status}` };
    }
    return {
      status: "fail",
      detail: `HTTP ${res.status} (expected ${verification.okIf})`,
    };
  } catch (e) {
    return {
      status: "fail",
      detail: e instanceof Error ? e.message : "Network error",
    };
  }
}
