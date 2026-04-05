import type { CreditCommandPlanPayload } from "@/lib/letterTypes";
import type { ProgressionPayload, WorkflowEnvelope } from "@/lib/workflowTypes";

export type PublicDemoScenario = {
  scenarioId: string;
  title: string;
  description: string;
  /** Machine grouping: general | law_backed | thin_file */
  category?: string;
  categoryLabel?: string;
};

export type PublicDemoStrategy = {
  source: string;
  rationale: string;
  roundSummary: string;
  selectedReviewClaimIds: string[];
  selectedCount: number;
  perClaim: Array<{
    reviewClaimId: string;
    rank: number;
    impactScore: number;
    /** Machine review type from engine (e.g. negative_impact). */
    reviewType?: string;
    /** Short plain-language line for public demo UI. */
    summary?: string;
  }>;
};

export type PublicDemoLetter = {
  id: number;
  bureau: string;
  bureauDisplay: string;
  preview: string;
  charCount: number;
  body: string;
};

export type PublicDemoIntake = {
  reports: Array<{
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
  }>;
  reviewClaims: unknown[];
  reviewClaimsCount: number;
  reviewClaimsTruncated?: boolean;
  reviewClaimsOmitted?: number;
  aggregates: {
    reportCount: number;
    totalAccountsExtracted: number;
    claimsByReviewType: Record<string, number>;
  };
};

/** POST /api/public/demo/run success payload (subset). */
export type PublicDemoRunResult = {
  ok: boolean;
  partial?: boolean;
  workflowId: string;
  scenarioId: string;
  scenarioTitle?: string;
  reportsProcessed?: number;
  intake?: PublicDemoIntake;
  strategy?: PublicDemoStrategy | null;
  letters: PublicDemoLetter[];
  creditCommandPlan: CreditCommandPlanPayload | null;
  message?: string;
  letterGenerationNote?: string | null;
  paymentWaived?: boolean;
  demoUserEmailMasked?: string;
  /** Canonical progression (aligned with consumer + org program APIs). */
  progression?: ProgressionPayload;
  /** Full engine envelope for this demo run (optional; includes nested progression). */
  workflow?: WorkflowEnvelope;
};
