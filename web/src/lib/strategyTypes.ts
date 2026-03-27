import type { ReviewClaimJson } from "@/lib/intakeTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type DisputeStrategyConstraints = {
  freePerBureauLimit: number;
  lettersBalance: number;
  isAdmin: boolean;
  usingFreeMode: boolean;
  hasUsedFreeLetters: boolean;
};

export type DisputeStrategyGroup = {
  reviewType: string;
  items: ReviewClaimJson[];
};

export type DisputeStrategyPayload = {
  roundNumber: number;
  eligibleCount: number;
  groups: DisputeStrategyGroup[];
  eligibleReviewClaimIds: string[];
  defaultSelectedReviewClaimIds: string[];
  suggestedReviewClaimIds: string[];
  deterministic: {
    source: string;
    rationale: string;
    roundSummary: string;
  } | null;
  constraints: DisputeStrategyConstraints;
};

export type DisputeStrategyBundle = {
  workflow: WorkflowEnvelope;
  selectionAllowed: boolean;
  selectionBlockedReason: string | null;
  disputeStrategy: DisputeStrategyPayload | null;
};
