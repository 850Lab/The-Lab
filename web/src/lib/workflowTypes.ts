/**
 * Subset of the FastAPI workflow envelope (services.workflow.responses.workflow_envelope).
 */

export type WorkflowStepStatusRow = {
  stepId: string;
  status: string;
  workflowStepId?: string;
  attemptCount?: number;
  [k: string]: unknown;
};

export type WorkflowStatePayload = {
  workflowId?: string;
  currentStep?: string;
  overallStatus?: string;
  userId?: number;
  workflowType?: string;
  [k: string]: unknown;
};

export type WorkflowEnvelope = {
  actionResult: string;
  workflowState: WorkflowStatePayload;
  stepStatus: WorkflowStepStatusRow[];
  userMessage: string;
  nextAvailableActions: Array<Record<string, unknown>>;
  asyncTaskState?: unknown;
  error?: unknown;
};
