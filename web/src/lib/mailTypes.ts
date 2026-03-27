import type { MailBureauTruthState, MailStatusPayload } from "@/lib/mailTruthTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type MailBureauTarget = {
  bureau: string;
  bureauDisplay: string;
  letterId: number;
  reportId: number;
  sendStatus: "pending" | "mailed";
  mailRowState: MailBureauTruthState;
  lobId: string;
  isTestSend: boolean;
  lobErrorMessageSafe: string;
  trackingNumber: string;
  trackingUrl: string;
  expectedDelivery: string;
};

export type MailContextPayload = {
  workflowHeadStepId: string | null;
  workflowPhase: string;
  mailStepStatus: string | null;
  mailStepFailed: boolean;
  onMailStep: boolean;
  mailGateExpected: number;
  mailGateConfirmedBureaus: string[];
  mailGateFailedSendCount: number;
  mailGateLastFailureMessageSafe: string;
  bureauTargets: MailBureauTarget[];
  pendingSendCount: number;
  mailedCount: number;
  hasLetters: boolean;
  proofBothOnFile: boolean;
  lobConfigured: boolean;
  lobTestMode: boolean;
  /** When true, customer sends are blocked unless Lob uses a live (non-test) key. */
  requiresLiveLobForCustomerSend: boolean;
  customerMailSendBlocked: boolean;
  customerMailSendBlockedReason: string;
  hasMailingsEntitlement: boolean;
  mailingsBalance: number;
  costEstimate: {
    totalCents?: number;
    totalDisplay?: string;
    breakdown?: string;
  };
  usStateOptions: string[];
  /** Single source of truth for mailing UI copy and gating hints. */
  mailStatus: MailStatusPayload;
};

export type MailContextResponse = {
  workflow: WorkflowEnvelope;
  mail: MailContextPayload;
};

export type MailFromAddressPayload = {
  name: string;
  address_line1: string;
  address_line2?: string;
  address_city: string;
  address_state: string;
  address_zip: string;
};

export type MailSendBureauPayload = {
  bureau: string;
  from_address: MailFromAddressPayload;
  return_receipt: boolean;
};

export type MailSendBureauResponse = {
  workflow: WorkflowEnvelope;
  lob: {
    lobId?: string;
    trackingNumber?: string;
    expectedDelivery?: string;
    isTest?: boolean;
  };
  mail: MailContextPayload;
};
