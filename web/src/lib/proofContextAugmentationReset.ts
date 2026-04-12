/**
 * Proof upload/signature responses omit optional AI fields; clear local state so stale
 * explanation/script copy is never shown after a refresh without those payloads.
 */
export function clearOptionalProofContextAugmentations(
  setAiExplanation: (v: unknown) => void,
  setAiScript: (v: unknown) => void,
  setProofSignalMeta?: (v: null) => void,
): void {
  setAiExplanation(null);
  setAiScript(null);
  setProofSignalMeta?.(null);
}
