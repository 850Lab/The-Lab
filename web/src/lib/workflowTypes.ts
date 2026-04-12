/**
 * FastAPI workflow: legacy envelope (workflow_envelope) + canonical ``progression`` slice
 * (services.workflow.progression_api.unified_progression_from_workflow_envelope).
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

/** Same shape for consumer, org program (when workflow-bound), and public demo. */
export type ProgressionPayload = {
  model: string;
  surface: string;
  actionResult?: string;
  workflowId?: string | null;
  workflowType?: string | null;
  overallStatus?: string;
  headStepId?: string | null;
  phase: string;
  linearOrder: string[];
  completedStepIds: string[];
  nextAvailableActions: Array<Record<string, unknown>>;
  error?: unknown;
};

/** Escalation slice on ``canonicalProgression.context`` (from ``escalation_summary_for_progression``). */
export type CanonicalProgressionEscalationSummary = {
  status: string;
  actionCount: number;
  primaryActionType?: string | null;
  primaryActionId?: string | null;
  triggers: string[];
};

/** Full canonical spine: context + head + integrity; embeds slim ``progression``. */
export type CanonicalProgressionPayload = {
  model: string;
  context: {
    surface: string;
    organizationProgramEnrollmentId?: number | null;
    organizationId?: number | null;
    demoLeadId?: number | null;
    escalation?: CanonicalProgressionEscalationSummary | null;
    [k: string]: unknown;
  };
  workflowId?: string | null;
  workflowType?: string | null;
  overallStatus?: string;
  currentStep?: string | null;
  stepStatus: WorkflowStepStatusRow[];
  nextAvailableActions: Array<Record<string, unknown>>;
  integrityHints?: unknown;
  progression?: ProgressionPayload;
};

/** Job + parse readiness — bundled on resume / intake (single sync surface). */
export type WorkflowSyncPayload = {
  activeReportParseJobs: Array<Record<string, unknown>>;
  lastReportParseJob: Record<string, unknown> | null;
  parseReadiness: {
    uploadStepStatus: string | null;
    parseStepStatus: string | null;
    asyncPhase: "idle" | "pending" | "running" | "steady";
  };
};

/** O.R.I.O.N. fragments on customer resume/progression envelopes (backend-owned intent). */
export type WorkflowOrionPayload = {
  guidance?: unknown;
  bestAction?: unknown;
  actionCandidates?: unknown;
  bestActionExplanation?: unknown;
  deliveryPrioritization?: unknown;
  uxSurfaceContract?: unknown;
};

export type WorkflowEnvelope = {
  actionResult: string;
  workflowState: WorkflowStatePayload;
  stepStatus: WorkflowStepStatusRow[];
  userMessage: string;
  nextAvailableActions: Array<Record<string, unknown>>;
  asyncTaskState?: unknown;
  error?: unknown;
  /** Canonical progression (mirror of workflowState + stepStatus); prefer for new UI. */
  progression?: ProgressionPayload;
  /** Same spine as consumer/org when backend attaches it. */
  canonicalProgression?: CanonicalProgressionPayload;
  /** Observability: active jobs + parse phase (resume / intake). */
  workflowSync?: WorkflowSyncPayload;
} & WorkflowOrionPayload;
