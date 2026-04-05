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

function findingsPriorityRank(reviewType: string): number {
  const i = FINDINGS_GROUP_PRIORITY.indexOf(reviewType);
  return i === -1 ? FINDINGS_GROUP_PRIORITY.length + 1 : i;
}

const REVIEW_TYPE_LABELS: Record<string, string> = {
  identity_verification: "Identity verification",
  account_ownership: "Account ownership",
  duplicate_account: "Duplicate accounts",
  negative_impact: "Negative impact",
  accuracy_verification: "Accuracy verification",
  unverifiable_information: "Unverifiable information",
};

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
    });
  }
  rows.sort(
    (a, b) =>
      findingsPriorityRank(a.reviewType) - findingsPriorityRank(b.reviewType) ||
      a.title.localeCompare(b.title),
  );
  return rows.map((r, i) => {
    const { reviewType: _rt, ...rest } = r;
    return {
      ...rest,
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
