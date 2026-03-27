import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type ReportIntakeRow = {
  reportId: number;
  bureau: string;
  fileName: string;
  uploadDate: string | null;
  counts: {
    accounts: number;
    negativeItems: number;
    hardInquiries: number;
    inquiries: number;
  };
};

/** Mirrors `ReviewClaim.to_dict()` from `review_claims.py` (subset used in UI). */
export type ReviewClaimJson = {
  review_claim_id: string;
  review_type: string;
  summary: string;
  question: string;
  entities: Record<string, string | null | undefined>;
};

export type CustomerIntakeSummary = {
  reports: ReportIntakeRow[];
  reviewClaims: ReviewClaimJson[];
  reviewClaimsCount: number;
  aggregates: {
    reportCount: number;
    totalAccountsExtracted: number;
    claimsByReviewType: Record<string, number>;
  };
};

export type IntakeSummaryBundle = {
  workflow: WorkflowEnvelope;
  intake: CustomerIntakeSummary;
};
