import type { ReviewClaimJson } from "@/lib/intakeTypes";
import type { ProgramEscalationPayload } from "@/lib/escalationProgramTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";

/** Slim escalation summary from engine (``escalation_public_view``). */
export type EscalationEngineView = {
  status: string;
  actions: unknown[];
  triggers: string[];
  triggerClaims: Record<string, string[]>;
  computedAt?: string | null;
};

export type EscalationGuidePayload = {
  pathGuidance: string;
  escalation: EscalationEngineView;
  programEscalation: ProgramEscalationPayload | null;
  nextRoundDispute: {
    eligibleItemCount: number;
    summarySafe: string;
  };
  differentiationNote: string;
};

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
  escalationGuide?: EscalationGuidePayload | null;
};
