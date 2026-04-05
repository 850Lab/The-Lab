import type { ProgramEscalationPayload } from "@/lib/escalationProgramTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type EscalationTrigger = {
  id: string;
  label: string;
  severity: string;
  detailSafe: string;
};

export type EscalationLeverageLink = {
  label: string;
  url: string;
};

export type EscalationLeverageAction = {
  id: string;
  title: string;
  tagline: string;
  whyNow: string;
  steps: string[];
  callScript: string;
  links: EscalationLeverageLink[];
  priority: number;
};

export type EscalationLayerPayload = {
  leverageHeadline: string;
  subcopy: string;
  triggers: EscalationTrigger[];
  actions: EscalationLeverageAction[];
  programEscalation?: ProgramEscalationPayload | null;
  latestResponse: {
    classification: string | null;
    escalationPrimaryPath: string | null;
    escalationReasoningSafe: string | null;
  } | null;
  context: {
    daysSinceFirstMailRaw: number;
    hasLiveMail: boolean;
    responsesRecordedAfterFirstMail: number;
    earliestMailedAt: string | null;
    trackStepCompleted: boolean;
  };
};

export type EscalationLayerResponse = {
  workflow: WorkflowEnvelope;
  escalationLayer: EscalationLayerPayload;
};
