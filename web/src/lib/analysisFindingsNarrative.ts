import type { ReviewClaimJson } from "@/lib/intakeTypes";

/**
 * Presentation-only: infer dominant issue flavor from existing claim text.
 * Does not add facts — keyword cues only, priority: collections → charge-off → late → general.
 */
export type DominantIssueKind = "collections" | "charge_off" | "late_payment" | "general";

export type AnalysisFindingsNarrative = {
  dominant: DominantIssueKind;
  headline: string;
  primaryTitle: string;
  primaryLines: [string, string];
  matchingCount: number;
  showHighImpact: boolean;
};

const TIER_COLLECTIONS = 1;
const TIER_CHARGE_OFF = 2;
const TIER_LATE = 3;
const TIER_GENERAL = 4;

function claimBlob(c: ReviewClaimJson): string {
  const parts = [c.summary, c.question, ...Object.values(c.entities || {})];
  return parts
    .filter((x): x is string => typeof x === "string" && x.trim().length > 0)
    .join(" ")
    .toLowerCase();
}

/** Smallest tier number = highest priority issue for this claim. */
export function issueTierForClaim(c: ReviewClaimJson): number {
  const t = claimBlob(c);
  if (
    /\b(collection|collections|collector|collectors|third[-\s]?party|placed for collection|sent to collection|collection account)\b/.test(
      t,
    )
  ) {
    return TIER_COLLECTIONS;
  }
  if (/\b(charge[-\s]?off|charged off|chargeoff|profit and loss)\b/.test(t)) {
    return TIER_CHARGE_OFF;
  }
  if (
    /\b(late payment|late payments|past due|delinq|delinquent|30[\s-]*day|60[\s-]*day|90[\s-]*day)\b/.test(
      t,
    )
  ) {
    return TIER_LATE;
  }
  return TIER_GENERAL;
}

function kindFromTier(tier: number): DominantIssueKind {
  if (tier === TIER_COLLECTIONS) return "collections";
  if (tier === TIER_CHARGE_OFF) return "charge_off";
  if (tier === TIER_LATE) return "late_payment";
  return "general";
}

export function resolveAnalysisNarrative(claims: ReviewClaimJson[]): AnalysisFindingsNarrative {
  const n = claims.length;
  if (n === 0) {
    return {
      dominant: "general",
      headline: "We found what's impacting your credit the most",
      primaryTitle: "Findings ready for review",
      primaryLines: [
        "Your report is organized — open the full list when you are ready.",
        "Nothing is disputed until you confirm what belongs in your round.",
      ],
      matchingCount: 0,
      showHighImpact: false,
    };
  }

  let bestTier = TIER_GENERAL;
  for (const c of claims) {
    bestTier = Math.min(bestTier, issueTierForClaim(c));
  }

  const dominant = kindFromTier(bestTier);
  const matchingClaims =
    dominant === "general"
      ? claims
      : claims.filter((c) => issueTierForClaim(c) === bestTier);
  const matchingCount = matchingClaims.length;

  const headline =
    dominant === "collections"
      ? "Collections are affecting your credit right now"
      : dominant === "charge_off"
        ? "Charge-offs are weighing on your profile"
        : dominant === "late_payment"
          ? "Late payments are holding your score back"
          : "We found what's impacting your credit the most";

  const primaryTitle =
    dominant === "collections"
      ? "Collection activity detected"
      : dominant === "charge_off"
        ? matchingCount === 1
          ? "Charge-off detected"
          : "Charge-offs detected"
        : dominant === "late_payment"
          ? "Late payment history surfaced"
          : "Items worth a closer look";

  const primaryLines: [string, string] =
    dominant === "collections"
      ? [
          `${matchingCount === 1 ? "One item" : `${matchingCount} items`} on your report ${matchingCount === 1 ? "ties" : "tie"} to collection reporting — lenders often read these as high risk.`,
          "We are not disputing anything yet; this is your private review list before the next step.",
        ]
      : dominant === "charge_off"
        ? [
            `${matchingCount === 1 ? "One charge-off" : `${matchingCount} charge-offs`} showed up in what we parsed — these entries can drag approvals and scores until they're verified.`,
            "You'll confirm what you recognize before anything is challenged.",
          ]
        : dominant === "late_payment"
          ? [
              `${matchingCount === 1 ? "One late-payment" : `${matchingCount} late-payment`} pattern${matchingCount === 1 ? "" : "s"} stood out — payment history is one of the heaviest score factors.`,
              "Review each line against your records; you choose what moves forward.",
            ]
          : [
              `We organized ${n} ${n === 1 ? "item" : "items"} from your report into a clear review list — negatives, accuracy flags, and duplicates grouped so nothing hides in the fine print.`,
              "Nothing is sent to the bureaus from this screen until you decide what belongs in your round.",
            ];

  return {
    dominant,
    headline,
    primaryTitle,
    primaryLines,
    matchingCount,
    showHighImpact: dominant !== "general",
  };
}
