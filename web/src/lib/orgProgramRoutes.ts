import type { ProgressResponse } from "@/lib/orgProgramTypes";

export {
  NAV_GUIDE_DESK,
  NAV_ORG_OVERVIEW,
  NAV_SETUP,
  PROGRAM_EYEBROW,
  PROGRAM_NAV,
  programStageLabel,
} from "./programExperienceCopy";

/** Primary next route for resume CTA (trusts backend ``nextStep`` / gates). */
export function primaryProgramPath(progress: ProgressResponse | null): string {
  if (!progress) return "/program";
  if (progress.instructorState?.paused || progress.effectiveState?.currentStep === "paused") {
    return "/program/progress";
  }
  const n = progress.nextStep ?? progress.effectiveState?.nextStep;
  if (n === "upload" || n === "enrollment") return "/program/upload";
  if (n === "findings_ready") return "/program/findings";
  if (n === "selections_saved") return "/program/select";
  if (n === "letters_generated") return "/program/letters";
  if (
    !n &&
    (progress.currentStep === "letters_generated" ||
      progress.effectiveState?.currentStep === "letters_generated")
  ) {
    return "/program/progress";
  }
  const g = progress.gates;
  if (g.mayGenerateLetters) return "/program/letters";
  if (g.mayUseDisputeFlow) return "/program/select";
  if (g.mayAnalyzeReport) return "/program/upload";
  if (g.mayUploadReport) return "/program/upload";
  return "/program/progress";
}
