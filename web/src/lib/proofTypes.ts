import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type ProofDocSummary = {
  id: number;
  fileName: string;
  fileType: string;
  docType: string;
  createdAt: string;
} | null;

export type ProofContextPayload = {
  hasGovernmentId: boolean;
  hasAddressProof: boolean;
  hasSignature: boolean;
  governmentId: ProofDocSummary;
  addressProof: ProofDocSummary;
  workflowHeadStepId: string | null;
  workflowPhase: string;
  proofStepStatus: string | null;
  proofStepCompleted: boolean;
  onProofAttachmentStep: boolean;
  allRequirementsMet: boolean;
};

/** Present only when proof context was requested with `includeAiExplanation=true`. */
export type ProofContextAiAugmentationFields = {
  aiExplanation: unknown;
  aiAugmentationStatus?: string;
  intelligentExplanationFamily?: string;
};

/** Present only when proof context was requested with `includeAiScript=true`. */
export type ProofContextScriptAugmentationFields = {
  aiScript: unknown;
  scriptAugmentationStatus?: string;
  intelligentScriptFamily?: string;
  /** Internal / debug-friendly: distinctiveness gate result for proof scripts (V2.3B). */
  proofScriptRefinementStatus?: string;
};

export type ProofContextResponse = {
  workflow: WorkflowEnvelope;
  proof: ProofContextPayload;
} & Partial<ProofContextAiAugmentationFields> &
  Partial<ProofContextScriptAugmentationFields>;
