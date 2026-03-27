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

export type ProofContextResponse = {
  workflow: WorkflowEnvelope;
  proof: ProofContextPayload;
};
