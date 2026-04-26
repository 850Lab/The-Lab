import type { FindingGroupCardProps } from "@/components/FindingGroupCard";
import type { DisputeGroupItem } from "@/components/DisputeGroupCard";
import type { ReviewClaimJson } from "@/lib/intakeTypes";
import { findingExpressionForReviewType } from "@/lib/intelligenceExpression";

/** Higher-impact / higher-urgency types first for findings (editorial sort, same data). */
const FINDINGS_GROUP_PRIORITY: string[] = [
  "negative_impact",
  "accuracy_verification",
  "duplicate_account",
  "identity_verification",
  "account_ownership",
  "unverifiable_information",
];

export function findingsPriorityRank(reviewType: string): number {
  const i = FINDINGS_GROUP_PRIORITY.indexOf(reviewType);
  return i === -1 ? FINDINGS_GROUP_PRIORITY.length + 1 : i;
}

/** Calmer display titles (same review_type keys; data unchanged). */
const REVIEW_TYPE_LABELS: Record<string, string> = {
  identity_verification: "Identity verification",
  account_ownership: "Account ownership",
  duplicate_account: "Duplicate accounts",
  negative_impact: "Score-impacting negatives",
  accuracy_verification: "Accuracy verification",
  unverifiable_information: "Unverifiable information",
};

/** Plain-language hint per category (editorial; same grouping as data). */
const WHAT_THIS_USUALLY_MEANS: Record<string, string> = {
  negative_impact:
    "These entries may be pulling your score or profile down until you verify them.",
  accuracy_verification:
    "Something about the reporting details may not match cleanly.",
  duplicate_account: "The same debt may be appearing more than once.",
  identity_verification: "Personal details may need cleanup before bigger disputes.",
  account_ownership: "Some accounts may need confirmation that they truly belong to you.",
  unverifiable_information: "Some details may be hard for a bureau to verify as shown.",
};

const CATEGORY_RECOMMENDATION: Record<string, string> = {
  negative_impact: "Recommended: review this early",
  accuracy_verification: "Recommended: verify only what you recognize",
  duplicate_account: "Recommended: compare balances and dates across listings",
  identity_verification: "Recommended: verify only what you recognize",
  account_ownership: "Recommended: use supporting documents if available",
  unverifiable_information: "Recommended: note what you can document",
};

export type FindingsPriorityBucket = "review_first" | "verify_carefully" | "lower_priority";

/** Maps review types to “Start here” columns without changing underlying claims. */
export function priorityBucketForReviewType(reviewType: string): FindingsPriorityBucket {
  const rt = reviewType || "unknown";
  if (rt === "negative_impact" || rt === "accuracy_verification") return "review_first";
  if (
    rt === "duplicate_account" ||
    rt === "identity_verification" ||
    rt === "account_ownership"
  ) {
    return "verify_carefully";
  }
  return "lower_priority";
}

function plainLanguageForReviewType(reviewType: string): string {
  return (
    WHAT_THIS_USUALLY_MEANS[reviewType] ??
    "Items in this group are organized for review — not a final dispute list."
  );
}

function recommendationForReviewType(reviewType: string): string {
  return (
    CATEGORY_RECOMMENDATION[reviewType] ?? "Recommended: scan and flag anything unfamiliar"
  );
}

export function labelForReviewType(reviewType: string): string {
  return REVIEW_TYPE_LABELS[reviewType] ?? reviewType.replace(/_/g, " ");
}

function displayCompany(c: ReviewClaimJson): string {
  const name = c.entities?.account_name;
  if (name && String(name).trim()) return String(name).trim();
  const bureau = c.entities?.bureau;
  if (bureau && String(bureau).trim()) return String(bureau).trim();
  return "Credit report item";
}

export function buildFindingGroupsFromClaims(
  claims: ReviewClaimJson[],
): FindingGroupCardProps[] {
  const byType = new Map<string, ReviewClaimJson[]>();
  for (const c of claims) {
    const k = c.review_type || "unknown";
    if (!byType.has(k)) byType.set(k, []);
    byType.get(k)!.push(c);
  }
  type Row = { reviewType: string } & FindingGroupCardProps;
  const rows: Row[] = [];
  for (const [reviewType, list] of byType) {
    const expr = findingExpressionForReviewType(reviewType);
    const items = list.map((c) => {
      const line = c.summary?.trim() || c.question?.trim() || c.review_claim_id;
      const bureau = c.entities?.bureau;
      return bureau ? `${line} — ${bureau}` : line;
    });
    rows.push({
      reviewType,
      title: labelForReviewType(reviewType),
      count: list.length,
      whyItMatters: expr.whyItMatters,
      whatWeSee: expr.whatWeSee,
      confidenceFraming: expr.confidenceFraming,
      items,
      plainLanguageHint: plainLanguageForReviewType(reviewType),
      recommendationLine: recommendationForReviewType(reviewType),
    });
  }
  rows.sort(
    (a, b) =>
      findingsPriorityRank(a.reviewType) - findingsPriorityRank(b.reviewType) ||
      a.title.localeCompare(b.title),
  );
  return rows.map((r, i) => {
    const { reviewType, ...rest } = r;
    return {
      ...rest,
      reviewType,
      featured: i === 0 && rest.count > 0,
    };
  });
}

export type DisputeGroupModel = {
  id: string;
  title: string;
  items: (DisputeGroupItem & { order: number })[];
};

export function buildDisputeGroupsFromClaims(
  claims: ReviewClaimJson[],
): DisputeGroupModel[] {
  const byType = new Map<string, ReviewClaimJson[]>();
  for (const c of claims) {
    const k = c.review_type || "unknown";
    if (!byType.has(k)) byType.set(k, []);
    byType.get(k)!.push(c);
  }
  let order = 0;
  const nextOrder = () => order++;
  const groups: DisputeGroupModel[] = [];
  for (const [reviewType, list] of byType) {
    list.sort((a, b) => (a.review_claim_id || "").localeCompare(b.review_claim_id || ""));
    groups.push({
      id: reviewType,
      title: labelForReviewType(reviewType),
      items: list.map((c) => ({
        id: c.review_claim_id,
        company: displayCompany(c),
        issueLabel: c.summary?.trim() || c.question?.trim() || "Review this item",
        order: nextOrder(),
      })),
    });
  }
  groups.sort(
    (a, b) =>
      findingsPriorityRank(a.id) - findingsPriorityRank(b.id) ||
      a.title.localeCompare(b.title),
  );
  return groups;
}
