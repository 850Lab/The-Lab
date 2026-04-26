/**
 * ORION system layer — behavior per program state (not chat; reflects system authority).
 */

export type OrionMode =
  | "announce"
  | "working"
  | "guide"
  | "confirm"
  | "handoff"
  | "idle";

export type OrionBehavior = {
  status: string;
  message: string;
  sub?: string;
  mode: OrionMode;
  rotating?: string[];
  nextAction?: string;
};

/** Program states that map to ORION behavior (intake + analysis + strategy entry). */
export type OrionBehaviorStateId =
  | "idle"
  | "PROGRAM_IDLE"
  | "INTAKE_OPEN"
  | "INTAKE_PARSE_IN_PROGRESS"
  | "INTAKE_AWAIT_ANALYZE"
  | "REPORT_PROCESSING"
  | "REPORT_PROCESSING_COMPLETE"
  | "ANALYSIS_INTRO"
  | "ANALYSIS_PRIORITIES"
  | "ANALYSIS_REVIEW"
  | "ANALYSIS_CONFIRMATION"
  | "STRATEGY_HANDOFF"
  | "STRATEGY_LOADING"
  | "STRATEGY_PREPARE";

export const ORION_BEHAVIOR: Record<OrionBehaviorStateId, OrionBehavior> = {
  idle: {
    mode: "idle",
    status: "Program",
    message: "Your program space is open.",
    nextAction: "Continue in the program.",
  },
  PROGRAM_IDLE: {
    mode: "idle",
    status: "Program active",
    message: "Your case is in progress. I'll guide you through the next step.",
    sub: "You can continue where you left off or move into the next phase.",
    nextAction: "Continue program",
  },
  INTAKE_OPEN: {
    mode: "guide",
    status: "Case intake",
    message: "Add your bureau PDF — I'll receive it into your program workspace.",
    sub: "One file or multiple parts; I'll merge and validate on intake.",
    nextAction: "Upload report",
  },
  INTAKE_PARSE_IN_PROGRESS: {
    mode: "working",
    status: "Receiving file",
    message: "I'm merging and checking your upload.",
    nextAction: "Hold here — no action needed yet.",
  },
  INTAKE_AWAIT_ANALYZE: {
    mode: "guide",
    status: "Report held",
    message: "Your PDF is stored securely for this cohort.",
    sub: "When you continue, I'll read it into a structured Case Review.",
    nextAction: "Start Case Review",
  },
  REPORT_PROCESSING: {
    mode: "working",
    status: "Analyzing report",
    message: "I'm reviewing your report now.",
    rotating: [
      "Scanning for negative accounts",
      "Checking inconsistencies",
      "Organizing prepared issues",
    ],
    nextAction: "Working in the background.",
  },
  REPORT_PROCESSING_COMPLETE: {
    mode: "announce",
    status: "Report ready",
    message: "Your report is in the program workspace.",
    sub: "I'm opening your Case Review now.",
    nextAction: "Entering guided review.",
  },
  ANALYSIS_INTRO: {
    mode: "announce",
    status: "Analysis complete",
    message: "I've finished analyzing your report.",
    sub: "I've prioritized what matters most for your correction path.",
    nextAction: "Review Case",
  },
  ANALYSIS_PRIORITIES: {
    mode: "guide",
    status: "Reviewing case",
    message: "I've organized your prepared issues by weight.",
    nextAction: "Walk the Case Review tiers.",
  },
  ANALYSIS_REVIEW: {
    mode: "guide",
    status: "Case walkthrough",
    message: "I'll introduce each prepared issue in order.",
    nextAction: "Advance when you're ready to continue.",
  },
  ANALYSIS_CONFIRMATION: {
    mode: "confirm",
    status: "Preparing case",
    message: "Confirm your Review Set so I can carry it into strategy.",
    nextAction: "Confirm Review Set",
  },
  STRATEGY_HANDOFF: {
    mode: "handoff",
    status: "Preparing strategy",
    message: "Your Review Set is organized for the next step.",
    nextAction: "Continue to Strategy",
  },
  STRATEGY_LOADING: {
    mode: "working",
    status: "Preparing strategy",
    message: "I'm opening your strategy workspace.",
    rotating: [
      "Reviewing your review set",
      "Organizing items for your correction plan",
    ],
    nextAction: "Working in the background.",
  },
  STRATEGY_PREPARE: {
    mode: "guide",
    status: "Review set ready",
    message: "I've prepared your strategy based on the issues we reviewed.",
    sub: "These items are now being organized into your correction plan.",
    nextAction: "Proceed with strategy",
  },
};
