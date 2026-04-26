import type { OrionFlowConfig } from "@/lib/orion/orionFlowConfig";

/**
 * ORION flow advancement by program state (intake + analysis).
 * Delays are clamped at runtime (see `orionProgramAdvancementTiming`).
 */
export const ORION_PROGRAM_FLOW = {
  INTAKE_OPEN: {
    mode: "guided",
    ctaDelayMs: 500,
  },
  INTAKE_PARSE_IN_PROGRESS: {
    mode: "guided",
    ctaDelayMs: 500,
  },
  INTAKE_AWAIT_ANALYZE: {
    mode: "guided",
    ctaLabel: "Read my report",
    ctaDelayMs: 550,
  },
  REPORT_PROCESSING: {
    mode: "guided",
    ctaDelayMs: 500,
  },
  REPORT_PROCESSING_COMPLETE: {
    mode: "auto",
    autoAdvanceTo: "ANALYSIS_INTRO",
    autoAdvanceDelayMs: 850,
  },
  ANALYSIS_INTRO: {
    mode: "guided",
    ctaLabel: "Review case",
    ctaDelayMs: 520,
  },
  ANALYSIS_PRIORITIES: {
    mode: "guided",
    ctaLabel: "Walk review set",
    ctaDelayMs: 450,
  },
  ANALYSIS_REVIEW: {
    mode: "guided",
    ctaDelayMs: 450,
  },
  ANALYSIS_CONFIRMATION: {
    mode: "blocked",
    ctaLabel: "Continue to Strategy",
    ctaDelayMs: 480,
    canAdvance: (ctx: unknown) => {
      if (typeof ctx !== "object" || ctx === null || !("confirmedCount" in ctx)) return false;
      const n = Number((ctx as { confirmedCount: unknown }).confirmedCount);
      return Number.isFinite(n) && n > 0;
    },
    blockedMessage:
      "At least one item must remain in your review set before I can prepare strategy.",
  },
  STRATEGY_HANDOFF: {
    mode: "guided",
    ctaLabel: "Continue to Strategy",
    ctaDelayMs: 600,
  },
} as const satisfies Record<string, OrionFlowConfig>;

export type OrionProgramFlowKey = keyof typeof ORION_PROGRAM_FLOW;

/** @deprecated Use ORION_PROGRAM_FLOW */
export const ORION_FLOW = ORION_PROGRAM_FLOW;
