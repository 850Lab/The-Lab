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
    ? "This was in the program's starting set for this round — it fits the filters we use after findings."
    : "This wasn't in the starting set; you can still add it if it matters for your situation.";
  return {
    ifSelected: `${rec} Including it means bureau-facing letters will argue this specific pattern this round.`,
    ifOmitted:
      "Leaving it out this round skips bureau letter text for this item now — you can often address it in a later round if your program allows.",
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
    "The program applies the same rules it used after findings: eligible items are the ones that cleared accuracy and impact checks for this round. You're confirming the final set, not guessing from scratch.";

  const outcome =
    "We expect bureaus to investigate what you mail. Outcomes range from deletion or correction to verification — timelines vary, and not every dispute wins.";

  const ifFails =
    "If responses are slow, thin, or unsatisfying, the next beats in your program are built for that: tracking, logging what came back, and escalation paths when you're stuck.";

  return [
    { title: "What we're doing", body: whatDoing },
    { title: "Why we're doing it", body: whyDoing },
    { title: "What we expect", body: outcome },
    { title: "If it doesn't land", body: ifFails },
  ];
}

/** Intro before letter list: ties findings → strategy → letters (no new data). */
export function lettersPurposeBlock(): { headline: string; paragraphs: string[] } {
  return {
    headline: "Here's what these letters are designed to do",
    paragraphs: [
      "Each letter is built from the same story we showed in findings and the dispute set you locked on the strategy screen — not a one-size template.",
      "They're meant to challenge specific reporting patterns bureau by bureau, using the items you included. Certified mail and proof come next in the program so sends are serious and complete.",
    ],
  };
}

export function postLettersWhatHappensNext(): { headline: string; bullets: string[] } {
  return {
    headline: "What happens next in your program",
    bullets: [
      "After you review letters, you'll move to proof and certified mail so disputes actually reach the bureaus.",
      "Bureaus typically have a limited window to respond after receipt; many replies land within a few weeks, some take longer — patience is normal.",
      "Use tracking for mail status, then record bureau mail or portal responses when they arrive — that unlocks the next guidance in the same workflow.",
      "If progress stalls or responses are weak, escalation tools in your program pick up where first-round letters leave off.",
    ],
  };
}

export function trackingQuietProgressMessage(): string {
  return (
    "Quiet stretches are normal: USPS and bureau intake don't send you daily updates. " +
    "Tracking here shows handoff and transit — not that a dispute analyst finished their review."
  );
}

export function trackingStatusGuideRows(): { status: string; meaning: string }[] {
  return [
    {
      status: "Not submitted",
      meaning: "No certified send on file yet for this bureau — mail step still pending or not started.",
    },
    {
      status: "Processing",
      meaning: "The mail partner accepted the job; carrier or print steps may still be in motion.",
    },
    {
      status: "Submitted — tracking pending",
      meaning: "Sent, but a public tracking link may not be available yet — check back after refresh.",
    },
    {
      status: "Submitted — tracking active",
      meaning: "Live mail with carrier visibility — watch transit; bureau review is a separate clock.",
    },
    {
      status: "Test — no USPS mail",
      meaning: "Sandbox or test key — nothing entered the real USPS certified stream.",
    },
    {
      status: "Send failed",
      meaning: "The submission didn't complete; retry from the mail step or contact support if it persists.",
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
