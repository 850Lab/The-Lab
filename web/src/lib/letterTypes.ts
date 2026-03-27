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
