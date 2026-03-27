import type { FindingGroupCardProps } from "@/components/FindingGroupCard";
import type { DisputeGroupItem } from "@/components/DisputeGroupCard";
import type { ReviewClaimJson } from "@/lib/intakeTypes";

const REVIEW_TYPE_LABELS: Record<string, string> = {
  identity_verification: "Identity verification",
  account_ownership: "Account ownership",
  duplicate_account: "Duplicate accounts",
  negative_impact: "Negative impact",
  accuracy_verification: "Accuracy verification",
  unverifiable_information: "Unverifiable information",
};

const REVIEW_TYPE_EXPLANATIONS: Record<string, string> = {
  identity_verification:
    "Personal or identifying details on your report that may need confirmation.",
  account_ownership: "Accounts where ownership or recognition should be confirmed.",
  duplicate_account: "Entries that may represent the same obligation more than once.",
  negative_impact: "Derogatory information that may be affecting your score.",
  accuracy_verification: "Balances, dates, or status lines that may need verification.",
  unverifiable_information: "Items that are hard to match to your own records.",
};

export function labelForReviewType(reviewType: string): string {
  return REVIEW_TYPE_LABELS[reviewType] ?? reviewType.replace(/_/g, " ");
}

function explanationForReviewType(reviewType: string): string {
  return (
    REVIEW_TYPE_EXPLANATIONS[reviewType] ??
    "Review this group using the questions shown for each item."
  );
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
  const out: FindingGroupCardProps[] = [];
  for (const [reviewType, list] of byType) {
    const items = list.map((c) => {
      const line = c.summary?.trim() || c.question?.trim() || c.review_claim_id;
      const bureau = c.entities?.bureau;
      return bureau ? `${line} — ${bureau}` : line;
    });
    out.push({
      title: labelForReviewType(reviewType),
      count: list.length,
      explanation: explanationForReviewType(reviewType),
      items,
    });
  }
  out.sort((a, b) => a.title.localeCompare(b.title));
  return out;
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
  groups.sort((a, b) => a.title.localeCompare(b.title));
  return groups;
}
