import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type EscalationRecommendation = {
  primary_path?: string;
  reasoning_safe?: string;
  factors?: string[];
  secondary_paths?: string[];
  priority?: string;
};

export type CustomerResponseRow = {
  responseId: string;
  receivedAt: string;
  sourceType: string;
  responseChannel: string;
  classificationStatus: string;
  classification: string | null;
  reasoningSafe: string | null;
  confidence: number | null;
  recommendedNextAction: string | null;
  escalationRecommendation: EscalationRecommendation;
  summarySafePreview: string;
  storageRef: string | null;
};

export type WorkflowResponsesListResponse = {
  workflow: WorkflowEnvelope;
  responses: CustomerResponseRow[];
  count: number;
};

/** DB-derived aggregates for the response intake flow (no raw response text). */
export type ResponseFlowMetrics = {
  totalResponses: number;
  classifiedSuccessCount: number;
  classifiedFailureCount: number;
  unclassifiedOrPendingCount: number;
  classificationSuccessRate: number | null;
  escalationRecommendedCount: number;
  escalationRate: number | null;
  latestResponseAt: string;
  latestClassificationStatus: string | null;
  latestResponseChannel: string | null;
  latestSourceType: string | null;
  latestRecommendedNextAction: string | null;
};

export type ResponseFlowPrimaryState =
  | "no_responses_yet"
  | "escalation_available"
  | "classification_issues_present"
  | "pending_review"
  | "monitoring_only";

/** Deterministic next-step copy from backend metrics (no raw response content). */
export type ResponseFlowGuidance = {
  primaryState: ResponseFlowPrimaryState;
  title: string;
  message: string;
  actionLabel?: string;
  actionTarget?: string;
};

export type WorkflowResponseMetricsResponse = {
  workflow: WorkflowEnvelope;
  metrics: ResponseFlowMetrics;
  guidance: ResponseFlowGuidance;
};

export type ResponseIntakeClassification = {
  label: string;
  reasoningSafe: string;
  confidence: number;
  recommendedNextAction: string;
};

export type ResponseIntakeSubmitResponse = {
  ok: boolean;
  responseId?: string;
  classification?: ResponseIntakeClassification | null;
  escalationRecommendation?: EscalationRecommendation | null;
  warning?: { code: string; messageSafe: string };
  workflow: WorkflowEnvelope;
};
