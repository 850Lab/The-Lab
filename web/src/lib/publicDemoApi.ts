import { workflowApiBase } from "@/lib/apiBase";
import type { PublicDemoRunResult, PublicDemoScenario } from "@/lib/publicDemoTypes";

export type HttpErrorContext = { status: number; statusText?: string };

/** Parsed FastAPI ``HTTPException`` JSON body (``detail`` may be object, string, or array). */
export function parseWorkflowApiErrorBody(
  text: string,
  http?: HttpErrorContext,
): {
  messageSafe: string;
  code?: string;
} {
  const statusLine = http
    ? `HTTP ${http.status}${http.statusText ? ` ${http.statusText}` : ""}`
    : "";

  try {
    const j = JSON.parse(text) as {
      detail?:
        | { messageSafe?: string; code?: string }
        | string
        | Array<{ msg?: string; type?: string }>;
    };
    const d = j.detail;
    if (typeof d === "string" && d.trim()) {
      return { messageSafe: d.trim() };
    }
    if (Array.isArray(d)) {
      const parts = d
        .map((item) =>
          item && typeof item === "object" && typeof item.msg === "string"
            ? item.msg
            : "",
        )
        .filter(Boolean);
      const joined = parts.join("; ").trim().slice(0, 500);
      if (joined) {
        return { messageSafe: joined };
      }
    }
    if (d !== null && typeof d === "object" && !Array.isArray(d)) {
      const code = typeof d.code === "string" ? d.code : undefined;
      const ms = d.messageSafe;
      if (typeof ms === "string" && ms.trim()) {
        return {
          messageSafe: ms.trim(),
          code,
        };
      }
      if (code) {
        return {
          messageSafe: code,
          code,
        };
      }
    }
  } catch {
    /* ignore */
  }

  const t = text.trim();
  if (t) {
    return { messageSafe: t.slice(0, 500) };
  }
  if (http) {
    return {
      messageSafe: `${statusLine} — empty or unreadable response body (often a reverse proxy or gateway in front of the API, or the workflow server is down).`,
    };
  }
  return {
    messageSafe:
      "Unknown error (no response body). Check the API URL, proxy, and that uvicorn is running.",
  };
}

export type PublicDemoUnavailableCopy = {
  headline: string;
  body: string;
  technicalNote?: string;
  code?: string;
  showOperatorDetails: boolean;
};

/**
 * Map fetch failures to visitor-facing copy plus optional API ``messageSafe`` (truthful).
 * ``showOperatorDetails`` is true in dev or when ``VITE_SHOW_DEMO_OPS_HINTS=1``.
 */
export function classifyPublicDemoScenariosError(e: unknown): PublicDemoUnavailableCopy {
  /** Collapsed ``<details>`` on the demo page; set ``VITE_HIDE_DEMO_OPS_HINTS=1`` to hide entirely. */
  const showOperatorDetails = import.meta.env.VITE_HIDE_DEMO_OPS_HINTS !== "1";

  const fromApi = (msg: string, code?: string): PublicDemoUnavailableCopy => {
    if (code === "PUBLIC_DEMO_UNAVAILABLE") {
      return {
        headline: "Interactive preview isn’t enabled on this server",
        body: "The demo uses the same parsing, disputes, letters, and gameplan as members — but this deployment hasn’t turned on the public demo yet. You can still start with your own account and report.",
        technicalNote: msg,
        code,
        showOperatorDetails,
      };
    }
    if (code === "PUBLIC_DEMO_NO_FIXTURES") {
      return {
        headline: "Sample PDFs aren’t on this server",
        body: "The live demo needs fixture files under ``samples/`` on the API host (see repo).",
        technicalNote: msg,
        code,
        showOperatorDetails,
      };
    }
    if (code === "DEMO_SECRET_INVALID") {
      return {
        headline: "Demo access is restricted",
        body: "This server expects a matching demo secret. Set VITE_PUBLIC_DEMO_SECRET in your web build to match PUBLIC_DEMO_SECRET on the API, then rebuild.",
        technicalNote: msg,
        code,
        showOperatorDetails,
      };
    }
    if (code === "INVALID_DEMO_RESPONSE") {
      return {
        headline: "Demo API returned something that isn’t JSON",
        body: `Usually the browser hit the wrong URL and got an HTML page (for example the app shell) instead of the workflow API. Check that the API is running and that Vite proxy / VITE_WORKFLOW_API_URL points at it. Current API base: ${workflowApiBase()}`,
        technicalNote: msg,
        code,
        showOperatorDetails,
      };
    }
    if (code === "WORKFLOW_API_PROXY_UNREACHABLE") {
      return {
        headline: "Workflow API isn’t running (or wrong port)",
        body: "Vite’s dev proxy could not connect to the FastAPI server. Start uvicorn on the target in web/.env.local (default 127.0.0.1:5000), or set WORKFLOW_API_PROXY_TARGET to match your API port.",
        technicalNote: msg,
        code,
        showOperatorDetails,
      };
    }
    if (
      /HTTP 50[234]|Bad Gateway|Gateway Timeout|empty or unreadable response/i.test(
        msg,
      )
    ) {
      return {
        headline: "Can’t reach the demo API (gateway or empty response)",
        body: `The browser got an error status but almost no JSON from the server — common when a proxy can’t reach the Python API, or the API crashed. Confirm uvicorn is up and the URL matches this app’s API base: ${workflowApiBase()}`,
        technicalNote: msg,
        code,
        showOperatorDetails,
      };
    }
    return {
      headline: "Couldn’t load the interactive preview",
      body: "The demo service returned an error. Check the technical note below, fix API config or networking, then retry.",
      technicalNote: msg,
      code,
      showOperatorDetails,
    };
  };

  if (e instanceof Error) {
    const ex = e as Error & { demoCode?: string; httpStatus?: number };
    if (
      e.message.includes("Failed to fetch") ||
      e.message.includes("NetworkError")
    ) {
      return {
        headline: "Can’t reach the demo API",
        body: `The page couldn’t load scenarios from the server. Often the browser is pointed at the wrong API host (Vite proxy or VITE_WORKFLOW_API_URL / VITE_WORKFLOW_API_PREFIX), or the API isn’t running. Current API base: ${workflowApiBase()}`,
        technicalNote: e.message,
        showOperatorDetails,
      };
    }
    if (ex.demoCode) {
      return fromApi(e.message, ex.demoCode);
    }
    const st = ex.httpStatus;
    const msg = e.message || "";
    if (
      msg.includes("Unexpected token") ||
      msg.includes("HTML instead of JSON") ||
      /not valid json/i.test(msg)
    ) {
      return {
        headline: "Demo API returned something that isn’t JSON",
        body: `Usually the browser hit the wrong URL and got an HTML page (for example the app shell) instead of the workflow API. Check that the API is running and that Vite proxy / VITE_WORKFLOW_API_URL points at it. Current API base: ${workflowApiBase()}`,
        technicalNote: msg.slice(0, 400),
        showOperatorDetails,
      };
    }
    if (typeof st === "number" && st >= 400) {
      return fromApi(msg || `HTTP ${st}`, ex.demoCode);
    }
    return {
      headline: "Couldn’t load the interactive preview",
      body: "Something went wrong while loading the demo. Try again, or continue with your own account.",
      technicalNote: msg,
      showOperatorDetails,
    };
  }
  const msg = String(e);
  return {
    headline: "Couldn’t load the interactive preview",
    body: "Something went wrong while loading the demo. Try again, or continue with your own account.",
    technicalNote: msg,
    showOperatorDetails,
  };
}

function demoHeaders(): Record<string, string> {
  const secret = (
    import.meta.env.VITE_PUBLIC_DEMO_SECRET as string | undefined
  )?.trim();
  const h: Record<string, string> = {};
  if (secret) {
    h["X-Public-Demo-Secret"] = secret;
  }
  return h;
}

export async function fetchPublicDemoScenarios(): Promise<PublicDemoScenario[]> {
  const base = workflowApiBase();
  const res = await fetch(`${base}/api/public/demo/scenarios`, {
    headers: demoHeaders(),
  });
  const text = await res.text();
  if (!res.ok) {
    const { messageSafe, code } = parseWorkflowApiErrorBody(text, {
      status: res.status,
      statusText: res.statusText,
    });
    const err = new Error(messageSafe) as Error & {
      demoCode?: string;
      httpStatus?: number;
    };
    err.demoCode = code;
    err.httpStatus = res.status;
    throw err;
  }
  const trimmed = text.trim();
  if (trimmed.startsWith("<")) {
    const err = new Error("API returned HTML instead of JSON.") as Error & {
      demoCode?: string;
      httpStatus?: number;
    };
    err.demoCode = "INVALID_DEMO_RESPONSE";
    err.httpStatus = res.status;
    throw err;
  }
  let j: { scenarios?: PublicDemoScenario[] };
  try {
    j = JSON.parse(text) as { scenarios?: PublicDemoScenario[] };
  } catch (parseErr) {
    const err = new Error(
      parseErr instanceof Error ? parseErr.message : "Invalid JSON",
    ) as Error & { demoCode?: string; httpStatus?: number };
    err.demoCode = "INVALID_DEMO_RESPONSE";
    err.httpStatus = res.status;
    throw err;
  }
  if (!Array.isArray(j.scenarios)) {
    const err = new Error(
      "Demo scenarios response is missing a scenarios array.",
    ) as Error & { demoCode?: string; httpStatus?: number };
    err.demoCode = "INVALID_DEMO_RESPONSE";
    err.httpStatus = res.status;
    throw err;
  }
  return j.scenarios;
}

export async function runPublicDemoScenario(
  scenarioId: string,
): Promise<PublicDemoRunResult> {
  const base = workflowApiBase();
  const res = await fetch(`${base}/api/public/demo/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...demoHeaders(),
    },
    body: JSON.stringify({ scenarioId }),
  });
  const text = await res.text();
  if (!res.ok) {
    let msg = text.slice(0, 500);
    try {
      const j = JSON.parse(text) as { detail?: { messageSafe?: string } };
      if (j.detail?.messageSafe) msg = j.detail.messageSafe;
    } catch {
      /* keep msg */
    }
    throw new Error(msg);
  }
  return JSON.parse(text) as PublicDemoRunResult;
}

export type PublicDemoLeadPayload = {
  name: string;
  email: string;
  phone: string;
  scenarioId?: string;
  workflowId?: string;
  intent?: string;
  organizationName?: string;
  audienceNote?: string;
  referrerName?: string;
};

export async function submitPublicDemoLead(
  payload: PublicDemoLeadPayload,
): Promise<{ ok: boolean; leadId: number | null }> {
  const base = workflowApiBase();
  const secret = (
    import.meta.env.VITE_PUBLIC_DEMO_SECRET as string | undefined
  )?.trim();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (secret) {
    headers["X-Public-Demo-Secret"] = secret;
  }
  const res = await fetch(`${base}/api/public/demo/lead`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      name: payload.name,
      email: payload.email,
      phone: payload.phone,
      scenarioId: payload.scenarioId,
      workflowId: payload.workflowId,
      intent: payload.intent,
      organizationName: payload.organizationName,
      audienceNote: payload.audienceNote,
      referrerName: payload.referrerName,
    }),
  });
  const text = await res.text();
  if (!res.ok) {
    let msg = text.slice(0, 500);
    try {
      const j = JSON.parse(text) as { detail?: { messageSafe?: string } };
      if (j.detail?.messageSafe) msg = j.detail.messageSafe;
    } catch {
      /* keep */
    }
    throw new Error(msg);
  }
  return JSON.parse(text) as { ok: boolean; leadId: number | null };
}
