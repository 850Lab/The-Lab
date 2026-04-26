import type { ReviewClaimJson } from "@/lib/intakeTypes";
import { findingExpressionForReviewType } from "@/lib/intelligenceExpression";
import {
  findingsPriorityRank,
  labelForReviewType,
  priorityBucketForReviewType,
  type FindingsPriorityBucket,
} from "@/lib/reviewClaimsDisplay";

export type ProgramAnalysisTierKey = FindingsPriorityBucket;

export const PROGRAM_ANALYSIS_TIER_ORDER: ProgramAnalysisTierKey[] = [
  "review_first",
  "verify_carefully",
  "lower_priority",
];

export const PROGRAM_ANALYSIS_TIER_LABEL: Record<ProgramAnalysisTierKey, string> = {
  review_first: "Highest Priority",
  verify_carefully: "Needs Review",
  lower_priority: "Additional Issues Found",
};

export const PROGRAM_ANALYSIS_ORION_STATUS: Record<ProgramAnalysisTierKey, string> = {
  review_first: "Prioritized for strategy",
  verify_carefully: "Needs confirmation",
  lower_priority: "Included in review set",
};

export type ProgramAnalysisFindingModel = {
  id: string;
  reviewType: string;
  title: string;
  summary: string;
  whyItMatters: string;
  orionStatus: string;
  tier: ProgramAnalysisTierKey;
  /** Plain-language framing for the guided review step (interpretive, not raw labels). */
  orionInterpretation: string;
};

function asClaim(raw: Record<string, unknown>): ReviewClaimJson {
  const entities = raw.entities;
  return {
    review_claim_id: String(raw.review_claim_id ?? ""),
    review_type: String(raw.review_type ?? "unknown"),
    summary: String(raw.summary ?? ""),
    question: String(raw.question ?? ""),
    entities:
      entities && typeof entities === "object" && !Array.isArray(entities)
        ? (entities as Record<string, string | null | undefined>)
        : {},
  };
}

function interpretationForClaim(c: ReviewClaimJson): string {
  const expr = findingExpressionForReviewType(c.review_type);
  const line = expr.whatWeSee.trim();
  if (line.length > 0) return line;
  return expr.whyItMatters.trim();
}

export function buildProgramAnalysisFindings(
  reviewClaims: Array<Record<string, unknown>>,
): ProgramAnalysisFindingModel[] {
  const models: ProgramAnalysisFindingModel[] = [];
  for (const raw of reviewClaims) {
    const c = asClaim(raw);
    if (!c.review_claim_id) continue;
    const tier = priorityBucketForReviewType(c.review_type);
    const title = labelForReviewType(c.review_type);
    const summary =
      c.summary?.trim() || c.question?.trim() || "Review this surfaced item with your records.";
    models.push({
      id: c.review_claim_id,
      reviewType: c.review_type,
      title,
      summary,
      whyItMatters: findingExpressionForReviewType(c.review_type).whyItMatters,
      orionStatus: PROGRAM_ANALYSIS_ORION_STATUS[tier],
      tier,
      orionInterpretation: interpretationForClaim(c),
    });
  }
  models.sort((a, b) => {
    const ta = PROGRAM_ANALYSIS_TIER_ORDER.indexOf(a.tier);
    const tb = PROGRAM_ANALYSIS_TIER_ORDER.indexOf(b.tier);
    if (ta !== tb) return ta - tb;
    const ra = findingsPriorityRank(a.reviewType) - findingsPriorityRank(b.reviewType);
    if (ra !== 0) return ra;
    return a.title.localeCompare(b.title) || a.id.localeCompare(b.id);
  });
  return models;
}

export function groupFindingsByTier(
  findings: ProgramAnalysisFindingModel[],
): Record<ProgramAnalysisTierKey, ProgramAnalysisFindingModel[]> {
  const out: Record<ProgramAnalysisTierKey, ProgramAnalysisFindingModel[]> = {
    review_first: [],
    verify_carefully: [],
    lower_priority: [],
  };
  for (const f of findings) {
    out[f.tier].push(f);
  }
  return out;
}
