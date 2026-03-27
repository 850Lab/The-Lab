/**
 * Shared customer-funnel language (Phase 4). Import where copy must stay aligned.
 */

export const PAYMENT_WHAT_HAPPENS_NEXT_LINES = [
  "Letters: we generate dispute letter text for this round (from your selection). Your purchase adds letter credits; generation is the next step after payment.",
  "Mail: certified send comes later — proof on file first, then you submit mail per bureau. Mailing uses credits if your pack includes them.",
  "Tracking: after a live send, USPS tracking appears here when the processor provides a number (carrier status, not proof the bureau finished).",
  "Responses: when mail or a notice arrives, record a short summary in this app — we classify it and show your next step.",
] as const;

export const NEXT_STEP_AFTER_PAYMENT_LINE =
  "Next step: generate your dispute letters for this round.";
