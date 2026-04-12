/**
 * Presentation-only copy and light structure for surfacing existing intelligence.
 * Does not infer new facts — maps review types and strategy payloads to guided language.
 */

import type { DisputeStrategyPayload } from "@/lib/strategyTypes";

export type FindingExpression = {
  whyItMatters: string;
  whatWeSee: string;
  confidenceFraming: string;
};

const DEFAULT_FINDING: FindingExpression = {
  whyItMatters:
    "Patterns here can affect how lenders read your file — worth challenging when they don't match reality.",
  whatWeSee:
    "We grouped similar line items from your report so the story is easier to follow than reading raw tradelines.",
  confidenceFraming:
    "Strength varies by item; your program still lets you include or skip anything before letters are built.",
};

const BY_REVIEW_TYPE: Record<string, FindingExpression> = {
  negative_impact: {
    whyItMatters:
      "Negative marks are often what drag scores and approvals — fixing inaccurate derogatories is high leverage when documentation supports you.",
    whatWeSee:
      "We pulled derogatory or high-impact entries the parser could tie to accounts, balances, or status lines on your report.",
    confidenceFraming:
      "These are commonly disputed when the underlying facts are wrong or incomplete — still review each line against your records.",
  },
  accuracy_verification: {
    whyItMatters:
      "Wrong balances, dates, or statuses can misrepresent payment history and utilization — that flows straight into scoring models.",
    whatWeSee:
      "We flagged fields where the report's numbers or timelines look inconsistent with typical reporting patterns or with each other.",
    confidenceFraming:
      "Mixed outcomes are normal; even weaker-looking items are still actionable when you have proof or clear contradictions.",
  },
  duplicate_account: {
    whyItMatters:
      "The same debt listed more than once can inflate balances and make you look riskier than you are.",
    whatWeSee:
      "We surfaced accounts or tradelines that may describe one obligation under multiple entries or creditors.",
    confidenceFraming:
      "Duplicate disputes are a standard bureau conversation when the linkage is clear — we still recommend you verify before locking the plan.",
  },
  identity_verification: {
    whyItMatters:
      "Names, addresses, or employer lines that aren't yours can signal mixed files or identity noise — worth cleaning before bigger disputes.",
    whatWeSee:
      "We isolated identity-related lines that don't match a clean single-consumer story from the rest of the file.",
    confidenceFraming:
      "Identity issues range from quick fixes to messy merges; treat these as foundation items in your round.",
  },
  account_ownership: {
    whyItMatters:
      "If you don't recognize an account, it shouldn't silently sit on your report as yours.",
    whatWeSee:
      "We marked tradelines where ownership, type, or creditor naming looks unclear relative to the rest of your history.",
    confidenceFraming:
      "Ownership challenges depend on what you recognize — include only what you genuinely dispute.",
  },
  unverifiable_information: {
    whyItMatters:
      "Items that can't be tied to something verifiable are harder for furnishers to defend when they're wrong.",
    whatWeSee:
      "We highlighted entries that look thin on detail or hard to match to a real creditor relationship.",
    confidenceFraming:
      "Weaker on paper can still be worth including when the story doesn't add up — pair with anything you can document.",
  },
};

export function findingExpressionForReviewType(reviewType: string): FindingExpression {
  return BY_REVIEW_TYPE[reviewType] ?? DEFAULT_FINDING;
}

export type SelectionImpact = { ifSelected: string; ifOmitted: string };

export function selectionImpactForReviewType(
  _reviewType: string,
  isRecommended: boolean,
): SelectionImpact {
  const rec = isRecommended
    ? "This is in the program's recommended starting set for this round."
    : "Optional — add only if it fits your priorities this round.";
  return {
    ifSelected: `${rec} Checked: your dispute package can include this item.`,
    ifOmitted:
      "Unchecked: skipped for this round — focused rounds are often stronger; you can revisit later if your program allows.",
  };
}

export type StrategyNarrativeSection = { title: string; body: string };

export function buildStrategyNarrative(
  strategy: DisputeStrategyPayload | null,
  themesText: string,
): StrategyNarrativeSection[] {
  if (!strategy || strategy.eligibleCount <= 0) {
    return [
      {
        title: "What we're doing",
        body: "When items become eligible again, this screen will outline the round plan in plain language.",
      },
    ];
  }

  const det = strategy.deterministic;
  const n = strategy.eligibleCount;
  const round = strategy.roundNumber;

  const whatDoing =
    det?.roundSummary?.trim() ||
    (round > 1
      ? `Round ${round}: we're lining up ${n} eligible dispute item(s) from your report — themes include ${themesText}.`
      : `We're lining up ${n} eligible dispute item(s) for this round — grouped around ${themesText}.`);

  const whyDoing =
    det?.rationale?.trim() ||
    "These items are the ones that cleared the same checks you already saw after findings. You're confirming direction — not inventing a strategy from scratch.";

  const outcome =
    "After you mail, bureaus investigate what you sent. Results vary: deletion, correction, or verification — timelines vary too, and not every dispute wins.";

  const ifFails =
    "If replies are slow or weak, your program keeps going: tracking, logging responses, and escalation options when you're stuck.";

  return [
    { title: "This round focuses on…", body: whatDoing },
    { title: "Why these items lead first", body: whyDoing },
    { title: "What to expect after you mail", body: outcome },
    { title: "If things move slowly", body: ifFails },
  ];
}

/** Intro before letter list: ties findings → strategy → letters (no new data). */
export function lettersPurposeBlock(): { headline: string; paragraphs: string[] } {
  return {
    headline: "What you’re looking at on this screen",
    paragraphs: [
      "Each letter is built from your findings and the items you confirmed in Strategy — draft dispute documents for you to review, not a one-size template.",
      "Proof and mailing come later in the same program. You stay in control of when things are sent.",
    ],
  };
}

export function postLettersWhatHappensNext(): { headline: string; bullets: string[] } {
  return {
    headline: "What happens next",
    bullets: [
      "You’ll add proof documents, then move toward mailing when you’re ready — nothing is sent until you complete those steps.",
      "Bureau response times vary after mail is received; your program keeps tracking and replies organized in one place.",
    ],
  };
}

export function trackingQuietProgressMessage(): string {
  return (
    "Quiet stretches are normal — USPS and bureaus don’t send daily updates. " +
    "This page is for watching movement and knowing what to expect, not constant change."
  );
}

export function trackingStatusGuideRows(): { status: string; meaning: string }[] {
  return [
    {
      status: "Not submitted",
      meaning: "No send on file for this bureau yet — finish mailing from the send step first.",
    },
    {
      status: "Processing",
      meaning: "The mail partner has the job; carrier steps may still be in motion.",
    },
    {
      status: "Submitted — tracking pending",
      meaning: "Sent, but a tracking link may not show yet — delivery updates can take a little time to appear.",
    },
    {
      status: "Submitted — tracking active",
      meaning: "Live mail with carrier visibility — watch transit here; bureau review is separate.",
    },
    {
      status: "Test — no USPS mail",
      meaning: "Test mode — nothing entered the real USPS stream.",
    },
    {
      status: "Send failed",
      meaning: "This send didn’t complete — you can retry from the mail step or contact support if it keeps happening.",
    },
  ];
}

/** Connects earlier program beats to escalation (editorial, honest). */
export function escalationProgramBridgeCopy(): string {
  return (
    "First-round letters and bureau replies don't always fix everything. " +
    "When responses are late, vague, or only half-address your items, stronger moves — furnisher disputes, structured follow-ups, and formal complaints — are the next layer. " +
    "Everything below builds on what you already mailed and logged; you're not starting from zero."
  );
}
