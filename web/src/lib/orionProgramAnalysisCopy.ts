import type { ProgramAnalysisPhase } from "@/lib/programAnalysisPhase";

/** Step strip labels — human, not enum names. */
export const PROGRAM_ANALYSIS_STEP_LABELS: Record<ProgramAnalysisPhase, string> = {
  ANALYSIS_INTRO: "Ready",
  ANALYSIS_PRIORITIES: "Priorities",
  ANALYSIS_REVIEW: "Walkthrough",
  ANALYSIS_CONFIRMATION: "Confirm",
  STRATEGY_HANDOFF: "Strategy",
};
