import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type PaymentPack = {
  id: string;
  label: string;
  price_cents: number;
  ai_rounds: number;
  letters: number;
  mailings: number;
};

export type PaymentAlaLetter = {
  id: string;
  label: string;
  price_cents: number;
  letters: number;
  ai_rounds: number;
  mailings: number;
};

export type PaymentContextPayload = {
  neededLetters: number;
  selectedDisputeItemCount: number | null;
  recommendedPack: PaymentPack;
  otherPacks: PaymentPack[];
  alaCarteLetters: PaymentAlaLetter[];
  entitlements: {
    letters: number;
    ai_rounds: number;
    mailings: number;
  };
  hasSufficientLetterEntitlement: boolean;
  paymentStepStatus: string | null;
  paymentStepCompleted: boolean;
  onPaymentStep: boolean;
  workflowHeadStepId: string | null;
  workflowPhase: string;
  stripeCheckoutAvailable: boolean;
  checkoutReturnOriginConfigured: boolean;
  catalogProductIds: string[];
  isAdmin: boolean;
  isFounder: boolean;
};

export type PaymentContextResponse = {
  workflow: WorkflowEnvelope;
  payment: PaymentContextPayload;
};

export type PaymentCheckoutResponse = {
  checkoutUrl: string;
  stripeCheckoutSessionId?: string;
  workflow: WorkflowEnvelope;
};

export type PaymentReconcileResponse = {
  workflow: WorkflowEnvelope;
  reconcile: {
    ok: boolean;
    alreadyProcessed?: boolean;
    /** False when credits applied but workflow payment step did not advance (retry reconcile). */
    paymentStepCompleted?: boolean;
    workflowIdFromSession?: string | null;
    productId?: string;
    error?: string;
  };
};
