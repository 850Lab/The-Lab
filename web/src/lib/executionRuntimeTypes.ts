/**
 * DTOs for GET/POST execution runtime endpoints (camelCase, aligned with workflow API JSON).
 */

export type ExecutionOutcomeOption = {
  id: string;
  label: string;
  outcomeKey: string;
  /** When present, sent as `notes` for predefined picks (engine still uses outcomeKey). */
  defaultNotes?: string;
};

export type PrimaryActiveBlock = {
  blockId: string;
  actionName: string;
  instructions: string;
  cautionNotes: string[];
};

export type ExecutionState = {
  runId: string;
  workflowId: string | null;
  blockedReason: string | null;
  activeBlockIds: string[];
  waitingBlockIds: string[];
  blockedBlockIds: string[];
  completedBlockIds: string[];
  primaryActiveBlock: PrimaryActiveBlock | null;
  outcomeOptions: ExecutionOutcomeOption[];
};

export type ExecutionProgressionPayload = {
  accepted: boolean;
  validationErrors: string[];
  state: Record<string, unknown>;
  activeBlockIds: string[];
  waitingBlockIds: string[];
  blockedBlockIds: string[];
  newlyActivatedBlockIds: string[];
  transitionNotes: string[];
};

export type ExecutionOutcomeSubmitBody = {
  blockId: string;
  outcomeKey: string;
  notes?: string;
  externalFlags?: Record<string, unknown>;
  source?: string;
};

export type ExecutionOutcomeResponse = {
  executionState: ExecutionState;
  progression: ExecutionProgressionPayload;
};

export type ExecutionStartResponse = {
  runId: string;
  executionState: ExecutionState;
};
