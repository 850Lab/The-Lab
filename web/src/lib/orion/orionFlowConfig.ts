/**
 * How ORION-driven program steps advance (850 Lab org program / analysis flow).
 * Wiring is optional — types define the contract for future UI + timers.
 */

export type OrionAdvanceMode = "auto" | "guided" | "blocked";

/** Alias for spec / external docs */
export type FlowMode = OrionAdvanceMode;

export type OrionFlowConfig<TContext = unknown> = {
  mode: OrionAdvanceMode;
  ctaLabel?: string;
  /** Guided / blocked: CTA reveal delay (clamped 400–700ms at runtime). */
  ctaDelayMs?: number;
  /** Route path or internal phase key, depending on caller convention. */
  autoAdvanceTo?: string;
  /** Auto: delay before advancing (clamped 700–1000ms at runtime). */
  autoAdvanceDelayMs?: number;
  /** Blocked: progression gate (e.g. counts / selections). */
  canAdvance?: (context: TContext) => boolean;
  blockedMessage?: string;
};

/** Alias for spec / external docs */
export type FlowConfig<TContext = unknown> = OrionFlowConfig<TContext>;
