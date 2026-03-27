export type NextRequiredAction =
  | "upload"
  | "pay"
  | "generate"
  | "proof"
  | "mail"
  | "track";

export type WorkflowIntegrityHints = {
  entitlementsButPaymentIncomplete: boolean;
  paymentCompletedButWrongStep: boolean;
  mailingDebitWithoutSend: boolean;
  proofIncomplete: boolean;
  mailBlocked: boolean;
  workflowStepMismatch: boolean;
  nextRequiredAction: NextRequiredAction;
};
