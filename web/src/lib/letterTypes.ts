import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type LetterRow = {
  id: number;
  reportId: number;
  bureau: string;
  bureauDisplay: string;
  createdAt: string;
  violationCount: number;
  categories: string[];
  preview: string;
  charCount: number;
};

export type LettersUiFlags = {
  workflowHeadStepId: string | null;
  workflowPhase: string;
  letterGenerationStepStatus: string | null;
  letterGenerationCompleted: boolean;
  onLetterGenerationStep: boolean;
  selectedReviewClaimCount: number;
};

export type LettersContextResponse = {
  workflow: WorkflowEnvelope;
  letters: LetterRow[];
  lettersUi: LettersUiFlags;
};

export type LettersGenerateResponse = {
  workflow: WorkflowEnvelope;
  generation: {
    bureaus: string[];
    billing?: unknown;
    readinessSummary: {
      includedDecisions: number;
      blockedDecisions: number;
    };
  };
};

export type CreditCommandPlanAction = {
  title: string;
  why: string;
  do_next: string;
  script?: string;
  warning?: string;
};

export type CreditCommandPlanDay = {
  label: string;
  actions: CreditCommandPlanAction[];
};

/** Mirrors ``credit_command_plan.build_credit_command_plan`` JSON shape. */
export type CreditCommandPlanPayload = {
  total_issues: number;
  high_impact: number;
  score_damaging: number;
  quick_wins: number;
  days: CreditCommandPlanDay[];
};

export type CreditCommandPlanResponse = {
  creditCommandPlan: CreditCommandPlanPayload | null;
  unavailableReason: string | null;
};
