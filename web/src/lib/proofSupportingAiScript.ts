/** ORION V2.2B — proof-only customer script; must be proof_submission_support. */

export type ProofSupportScriptLine = { speaker: "user"; text: string };

export type CustomerProofSupportScript = {
  scriptIntent: "proof_submission_support";
  title: string;
  intro: string | null;
  lines: ProofSupportScriptLine[];
  talkingPoints: string[];
  tone: "clear" | "supportive" | "firm" | "calm";
};

const TONES = new Set(["clear", "supportive", "firm", "calm"]);

function isUserLine(row: unknown): row is ProofSupportScriptLine {
  if (!row || typeof row !== "object") return false;
  const o = row as Record<string, unknown>;
  return o.speaker === "user" && typeof o.text === "string" && o.text.trim().length > 0;
}

/**
 * Null-safe parse for proof-context `aiScript`. Rejects wrong intents and invalid shapes.
 */
export function safeCustomerProofSupportScript(raw: unknown): CustomerProofSupportScript | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  if (o.scriptIntent !== "proof_submission_support") return null;
  if (typeof o.title !== "string" || !o.title.trim()) return null;
  if (o.intro != null && typeof o.intro !== "string") return null;
  if (!TONES.has(String(o.tone))) return null;
  if (!Array.isArray(o.lines)) return null;
  const lines: ProofSupportScriptLine[] = [];
  for (const row of o.lines) {
    if (!isUserLine(row)) return null;
    lines.push({ speaker: "user", text: row.text.trim() });
  }
  if (!Array.isArray(o.talkingPoints)) return null;
  const tps: string[] = [];
  for (const p of o.talkingPoints) {
    if (typeof p !== "string" || !p.trim()) return null;
    tps.push(p.trim());
  }
  if (lines.length === 0 && tps.length === 0) return null;
  return {
    scriptIntent: "proof_submission_support",
    title: o.title.trim(),
    intro: o.intro == null ? null : String(o.intro).trim() || null,
    lines,
    talkingPoints: tps,
    tone: o.tone as CustomerProofSupportScript["tone"],
  };
}
