/** Calm, bounded delays for ORION program flow (no typing effects). */

export const ORION_CTA_REVEAL_MIN_MS = 400;
export const ORION_CTA_REVEAL_MAX_MS = 700;

export const ORION_AUTO_ADVANCE_MIN_MS = 700;
export const ORION_AUTO_ADVANCE_MAX_MS = 1000;

export function clampCtaRevealMs(ms: number | undefined): number {
  const v = ms ?? Math.round((ORION_CTA_REVEAL_MIN_MS + ORION_CTA_REVEAL_MAX_MS) / 2);
  return Math.min(ORION_CTA_REVEAL_MAX_MS, Math.max(ORION_CTA_REVEAL_MIN_MS, v));
}

export function clampAutoAdvanceMs(ms: number | undefined): number {
  const v = ms ?? Math.round((ORION_AUTO_ADVANCE_MIN_MS + ORION_AUTO_ADVANCE_MAX_MS) / 2);
  return Math.min(ORION_AUTO_ADVANCE_MAX_MS, Math.max(ORION_AUTO_ADVANCE_MIN_MS, v));
}
