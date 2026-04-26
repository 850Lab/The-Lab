/**
 * Shared customer-funnel language — payment tied to value moments, not arbitrary gates.
 */

/** Shown on upload, report, letters — clarifies free prep vs paid execution. */
export const FREE_VALUE_LINE =
  "You can download your letters and send them yourself, or we can handle mailing and tracking for you in the program when you’re ready.";

export const TRUST_SIGNALS_BEFORE_UPLOAD = [
  "Encrypted upload",
  "We don’t send anything without your approval",
  "No bureau contact from this step",
] as const;

export const POST_DOWNLOAD_NEXT_STEPS = [
  "Print or save your letter file",
  "Include any proof your letters reference",
  "Mail to the addresses on each letter",
  "Keep copies and mailing proof",
  "Use tracking or responses in the app when mail is out",
] as const;

export const POST_DOWNLOAD_UPGRADE_LINE =
  "We can walk you through mailing and tracking in the next steps when you continue in the program — or keep going on your own with your download.";

export const PAYMENT_WHAT_HAPPENS_NEXT_LINES = [
  "This covers preparing and packaging your round — not a fee to “buy” the letters as files; you can still download and review them in the app.",
  "You’re moving toward optional certified mail, tracking, and a guided path so you don’t juggle it all manually.",
  "Nothing is mailed at checkout. Mailing and tracking use your balance only when you choose to send, after proof is in place.",
  "After payment you continue in the same program — proof, then send or download, then responses and tracking as things come back.",
] as const;

export const NEXT_STEP_AFTER_PAYMENT_LINE =
  "Next: your letter package is prepared from this round — review and download before anything is sent.";
