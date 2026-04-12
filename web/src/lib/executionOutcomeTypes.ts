/**
 * Guided execution outcome logging — UI payload shape.
 * Map to `submit_execution_outcome(run_id, OutcomeSubmission)` when execution runtime is wired.
 */
export type OutcomeLoggingPhase = "choose" | "other_detail" | "submitting" | "acknowledged";

export type OutcomeSubmitPayload =
  | { kind: "predefined"; outcomeId: string }
  | { kind: "other"; text: string; notSure: boolean };

export const OTHER_OUTCOME_TEXT_MAX = 200;
