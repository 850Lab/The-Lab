/**
 * Shared customer-funnel language — payment tied to value moments, not arbitrary gates.
 */

export const PAYMENT_WHAT_HAPPENS_NEXT_LINES = [
  "Letter moment: you only pay when the plan is real — next screen generates bureau-ready dispute text from your selection (credits from this purchase or ones you already have).",
  "Certified mail moment: mailing balance from your pack is used when you choose to submit each bureau — after proof is on file. No surprise charge at send unless you need more mailings on your account.",
  "Tracking moment: after a live send, USPS status shows handoff and transit here when the processor returns a number — separate from bureau review.",
  "Response moment: when a letter or notice lands, you log a short summary — we classify it and point you to the next move in the same program.",
] as const;

export const NEXT_STEP_AFTER_PAYMENT_LINE =
  "Next up: letter generation from the plan you locked — the deliverable you just paid for.";
