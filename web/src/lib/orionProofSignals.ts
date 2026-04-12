/** ORION V2.4 — Proof script observability (names must match backend). */

import { workflowApiBase } from "@/lib/apiBase";

export const ORION_PROOF_SCRIPT_RENDERED = "orion_proof_script_rendered";
export const ORION_PROOF_SCRIPT_VISIBLE = "orion_proof_script_visible";
export const ORION_PROOF_SCRIPT_INTERACTED = "orion_proof_script_interacted";
export const ORION_PROOF_STEP_COMPLETED = "orion_proof_step_completed";

export type OrionProofSignalContext = {
  token: string;
  workflowId: string;
  contractCompleteness: string;
  scriptAugmentationStatus?: string | null;
  proofScriptRefinementStatus?: string | null;
};

export function buildOrionProofSignalMetadata(ctx: OrionProofSignalContext): Record<string, unknown> {
  return {
    scriptAugmentationStatus: ctx.scriptAugmentationStatus ?? null,
    proofScriptRefinementStatus: ctx.proofScriptRefinementStatus ?? null,
    contractCompleteness: ctx.contractCompleteness,
  };
}

/**
 * Fire-and-forget POST; never throws; ignores response body.
 */
export function sendOrionProofSignal(
  ctx: OrionProofSignalContext,
  event: string,
  extraMetadata?: Record<string, unknown>,
): void {
  const url = `${workflowApiBase()}/api/workflows/${encodeURIComponent(ctx.workflowId)}/observability/orion-signal`;
  const metadata = { ...buildOrionProofSignalMetadata(ctx), ...extraMetadata };
  void fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${ctx.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      event,
      timestamp: new Date().toISOString(),
      metadata,
    }),
  }).catch(() => {});
}
