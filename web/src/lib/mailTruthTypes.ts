/** Authoritative mail funnel states from GET .../mail/context ``mailStatus`` (backend only). */

export type MailPrimaryState =
  | "no_letters"
  | "proof_required"
  | "ready_to_send"
  | "send_blocked"
  | "sending_failed"
  | "partially_sent"
  | "sent_test"
  | "sent_live"
  | "tracking_available"
  | "sent_mixed";

export type MailBureauTruthState =
  | "pending"
  | "processing"
  | "sending_failed"
  | "sent_test"
  | "sent_live"
  | "tracking_available";

export type MailStatusPayload = {
  primaryState: MailPrimaryState;
  title: string;
  message: string;
  isBlocked: boolean;
  isTestMode: boolean;
  requiresLiveForCustomerSend: boolean;
  hasTracking: boolean;
  lettersGenerated: boolean;
  proofComplete: boolean;
  mailingCreditsAvailable: boolean;
  pendingBureauCount: number;
  mailedBureauCount: number;
  perBureau: Array<{
    bureauKey: string;
    state: MailBureauTruthState;
    trackingUrl: string;
    lobId: string;
    isTest: boolean;
    trackingNumber: string;
    expectedDelivery: string;
    errorMessageSafe?: string;
  }>;
};
