/**
 * Canonical ORION strings for org program intake + analysis (850 Lab).
 * Presentation-only — does not change backend findings.
 */
export const ORION = {
  INTAKE_PARSE_IN_PROGRESS: {
    status: "Receiving your file",
    message: "I'm merging and checking your upload.",
    nextAction: "Stay on this page — you don't need to tap anything yet.",
  },
  INTAKE_AWAIT_ANALYZE: {
    status: "Report saved",
    message: "Your PDF is stored securely.",
    sub: "When you're ready, I'll read it into structured findings.",
    nextAction: "Tap below when you want me to start reading.",
  },
  REPORT_PROCESSING: {
    status: "Analyzing your report",
    message: "I'm reviewing your report now.",
    rotating: [
      "Scanning for negative accounts",
      "Checking inconsistencies",
      "Organizing findings",
    ],
    nextAction: "This runs quietly in the background.",
  },
  REPORT_PROCESSING_COMPLETE: {
    status: "Report ready",
    message: "I've pulled your report into the program.",
    sub: "Opening your analysis workspace.",
    nextAction: "I'll move you into your guided review automatically.",
  },
  ANALYSIS_INTRO: {
    status: "Analysis complete",
    message: "I've finished analyzing your report.",
    sub: "I found the issues affecting your profile.",
    nextAction: "When you're ready, we'll walk priorities together.",
  },
  ANALYSIS_PRIORITIES: {
    status: "Reviewing your case",
    message: "I prioritized the issues that matter most.",
    nextAction: "Walk the tiers when you're ready to continue.",
  },
  ANALYSIS_REVIEW: {
    status: "Walking through findings",
    message: "I'll show you what's impacting your profile.",
    nextAction: "Use Next to move through each item in order.",
  },
  ANALYSIS_CONFIRMATION: {
    status: "Preparing your case",
    message: "Confirm these so I can build your strategy.",
    nextAction: "Keep at least one item in your review set to continue.",
  },
  STRATEGY_HANDOFF: {
    status: "Preparing strategy",
    message: "I'm building your correction strategy now.",
    nextAction: "Continue when you're ready to open the strategy step.",
  },
} as const;

export type OrionPhaseKey = keyof typeof ORION;

export type OrionProgramAnalysisLines = {
  status: string;
  message: string;
  sub?: string;
  nextAction?: string;
  rotating?: readonly string[];
};
