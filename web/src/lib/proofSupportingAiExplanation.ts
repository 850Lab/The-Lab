/** ORION V2.1B — nullable customer augmentation; never authoritative over deterministic ORION. */

export type CustomerAiExplanationGroundedIn = {
  bestActionKey?: string | null;
  explanationType?: string | null;
  guidanceType?: string | null;
};

export type CustomerAiExplanation = {
  headline: string;
  body: string;
  nextStepLabel?: string | null;
  tone: "supportive" | "urgent" | "calm" | "clear";
  groundedIn: CustomerAiExplanationGroundedIn;
};

const TONES = new Set(["supportive", "urgent", "calm", "clear"]);

function isNonEmptyString(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

/**
 * Null-safe parse for optional proof-context `aiExplanation`.
 * Returns null for missing, invalid, or empty usable copy.
 */
export function safeCustomerAiExplanation(raw: unknown): CustomerAiExplanation | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (!isNonEmptyString(o.headline) || !isNonEmptyString(o.body)) return null;
  if (!TONES.has(String(o.tone))) return null;
  const gi = o.groundedIn;
  if (!gi || typeof gi !== "object") return null;
  const g = gi as Record<string, unknown>;
  for (const k of ["bestActionKey", "explanationType", "guidanceType"] as const) {
    const v = g[k];
    if (v != null && typeof v !== "string") return null;
  }
  return {
    headline: o.headline,
    body: o.body,
    nextStepLabel:
      o.nextStepLabel == null
        ? null
        : typeof o.nextStepLabel === "string"
          ? o.nextStepLabel
          : null,
    tone: o.tone as CustomerAiExplanation["tone"],
    groundedIn: {
      bestActionKey: (g.bestActionKey as string | null | undefined) ?? null,
      explanationType: (g.explanationType as string | null | undefined) ?? null,
      guidanceType: (g.guidanceType as string | null | undefined) ?? null,
    },
  };
}

/** Non-empty supporting copy for UI, or null to render nothing. */
export function pickProofMoreContextCopy(ai: unknown): { headline: string; body: string } | null {
  const x = safeCustomerAiExplanation(ai);
  if (!x) return null;
  const headline = x.headline.trim();
  const body = x.body.trim();
  if (!headline && !body) return null;
  return {
    headline: headline || "More context",
    body: body || headline,
  };
}
