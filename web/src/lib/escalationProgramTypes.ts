/** Program escalation UX (``escalation_ux_v1``) — same workflow, metadata-backed state. */

export type ProgramEscalationAffectedItem = {
  reviewClaimId: string;
  line: string;
};

export type ProgramEscalationActionRow = {
  id: string;
  type: string;
  priority?: number;
  triggerReason?: string;
  title: string;
  summarySafe?: string;
  reviewClaimIds?: string[];
  affectedItems?: ProgramEscalationAffectedItem[];
  claimSummaryLines?: string[];
  documentDraft?: string;
  callBullets?: string[];
  metadata?: Record<string, unknown>;
  userMarkedReviewed?: boolean;
  userMarkedProceeded?: boolean;
};

export type ProgramEscalationGroup = {
  triggerKey: string;
  triggerLabel: string;
  why: string;
  actions: ProgramEscalationActionRow[];
};

export type ProgramEscalationPayload = {
  model: string;
  status: string;
  triggers: string[];
  groups: ProgramEscalationGroup[];
  continueProgramNote: string;
  differentiationNote: string;
};
