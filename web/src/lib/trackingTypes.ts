import type { WorkflowEnvelope } from "@/lib/workflowTypes";

/** One resolved mail target + latest ``lob_sends`` row (see ``customer_tracking_service``). */
export type TrackingBureauRow = {
  bureau: string;
  bureauDisplay: string;
  reportId: string | number | null;
  rowStatus: "not_mailed" | "mailed" | "error" | "other";
  displayStatus: string;
  trackingNumber: string;
  trackingUrl: string;
  expectedDelivery: string;
  mailedAt: string;
  lobDbStatus: string;
  errorMessage: string;
  isTestSend: boolean;
  lobId: string;
};

export type TrackingHomeSummaryCompact = {
  nextBestAction?: string | null;
  waitingOn?: string | null;
  failedStep?: string | null;
  safeRouteHint?: string | null;
  responseStatus?: string | null;
  currentStepId?: string | null;
  overallStatus?: string | null;
  linearPhase?: string | null;
  stalled?: boolean | null;
  escalationAvailable?: boolean | null;
};

export type TrackingContextPayload = {
  authoritativeHeadStepId: string | null;
  linearPhase: string | null;
  mailStepStatus: string | null;
  trackStepStatus: string | null;
  onTrackStep: boolean;
  trackStepCompleted: boolean;
  mailGateExpected: number;
  mailGateConfirmedBureaus: string[];
  mailGateFailedSendCount: number;
  mailGateLastFailureMessageSafe: string;
  bureauRows: TrackingBureauRow[];
  mailedBureauCount: number;
  notMailedBureauCount: number;
  hasTargets: boolean;
  timeline: {
    earliestMailedAt: string;
    daysSinceFirstMail: number;
    timelineTotalDays: number;
  };
  homeSummary: TrackingHomeSummaryCompact | null;
  trackingStatus: {
    title: string;
    message: string;
    hasLiveSubmissions: boolean;
    hasTestSubmissionsOnly: boolean;
    hasTrackingLink: boolean;
  };
};

export type TrackingContextResponse = {
  workflow: WorkflowEnvelope;
  tracking: TrackingContextPayload;
};

/** Modal detail slice (subset of ``TrackingBureauRow``). */
export type TrackingModalBureau = Pick<
  TrackingBureauRow,
  | "bureauDisplay"
  | "rowStatus"
  | "displayStatus"
  | "trackingNumber"
  | "trackingUrl"
  | "expectedDelivery"
  | "mailedAt"
  | "errorMessage"
  | "lobDbStatus"
  | "isTestSend"
  | "lobId"
>;
