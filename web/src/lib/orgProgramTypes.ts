/** Shapes from FastAPI org-program routes (camelCase where backend emits it). */

import type { ProgressionPayload } from "@/lib/workflowTypes";

export type OrgProgramResponse = {
  organization: {
    id: number;
    name: string;
    status: string;
    contactEmail?: string | null;
    contactPhone?: string | null;
    programCode?: string | null;
    onboardingStage?: string | null;
    paymentAccess?: string | null;
    programAccessAllowed?: boolean;
    programAccessActivatedAt?: string | null;
  } | null;
  membership: {
    organizationId: number;
    role: string;
    status: string;
  } | null;
  enrollment: {
    id: number;
    enrollmentId?: number;
    status: string;
    enrolledAt?: string | null;
    activatedAt?: string | null;
    completedAt?: string | null;
    /** Authoritative org program workflow (``org_program_v1``). */
    programWorkflowId?: string | null;
  } | null;
};

export type ProgressStateSlice = {
  currentStep: string;
  nextStep: string | null;
  completedSteps: string[];
};

export type ProgressResponse = {
  organizationProgramEnrollmentId: number;
  systemState: ProgressStateSlice;
  instructorState: {
    paused: boolean;
    overrideKind: string | null;
    overrideStep: string | null;
    overrideAt?: string | null;
    overrideByUserId?: number | null;
    overrideReasonSafe?: string | null;
  };
  effectiveState: ProgressStateSlice;
  currentStep: string;
  nextStep: string | null;
  completedSteps: string[];
  gates: {
    mayUploadReport: boolean;
    mayAnalyzeReport: boolean;
    mayUseDisputeFlow: boolean;
    mayGenerateLetters: boolean;
  };
  stepTimestamps: Record<string, string | null | undefined>;
  programAccess?: {
    allowed: boolean;
  };
  /** Engine snapshot (``org_program_v1``); same contract as consumer ``progression``. */
  progression?: ProgressionPayload;
};

/** Program stages (matches backend ``PROGRAM_STEPS`` order). */
export const PROGRAM_STAGE_ORDER = [
  "enrollment",
  "upload",
  "findings_ready",
  "selections_saved",
  "letters_generated",
] as const;

export type ReportUploadResponse = {
  ok: boolean;
  processingStatus: string;
  reportsProcessed: number;
  reportIds: number[];
  fileSkips: unknown[];
  progression?: ProgressionPayload;
};

export type FindingsResponse = {
  processingStatus: string;
  reportId: number | null;
  summary: Record<string, unknown> | null;
  reviewClaims: Array<Record<string, unknown>>;
  violations: unknown[];
  progression?: ProgressionPayload;
};

export type DisputeStrategyGroup = {
  reviewType: string;
  items: Array<Record<string, unknown>>;
};

export type DisputeOptionsResponse = {
  reportId: number | null;
  selectionAllowed: boolean;
  selectionBlockedReason: string | null;
  disputeStrategy: {
    roundNumber: number;
    eligibleCount: number;
    groups: DisputeStrategyGroup[];
    eligibleReviewClaimIds: string[];
    defaultSelectedReviewClaimIds: string[];
    suggestedReviewClaimIds: string[];
    constraints?: Record<string, unknown>;
  } | null;
  progression?: ProgressionPayload;
};

export type GenerateLettersResponse = {
  generationStatus: string;
  reportId: number;
  selectedItemCount: number;
  billing: Record<string, unknown>;
  letters: unknown[];
  bureauKeys: string[];
  progression?: ProgressionPayload;
};
