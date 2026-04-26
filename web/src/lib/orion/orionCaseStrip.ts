import type { ProgressResponse } from "@/lib/orgProgramTypes";

export type OrionCaseStripTone = "complete" | "current" | "upcoming";

export type OrionCaseStripItem = {
  id: string;
  label: string;
  tone: OrionCaseStripTone;
};

export type OrionCaseStripContext = {
  enrolled: boolean;
  reportAnalyzed: boolean;
  reviewSetPrepared: boolean;
  strategyStepActive: boolean;
};

/** Map org program progress to the linear case strip (hub + continuity). */
export function caseStripContextFromProgramProgress(progress: ProgressResponse | null): OrionCaseStripContext {
  if (!progress) {
    return {
      enrolled: true,
      reportAnalyzed: false,
      reviewSetPrepared: false,
      strategyStepActive: false,
    };
  }
  const cur = String(progress.effectiveState?.currentStep ?? progress.currentStep ?? "");
  const done = new Set(progress.completedSteps ?? []);

  const reportAnalyzed =
    done.has("findings_ready") ||
    ["findings_ready", "selections_saved", "letters_generated"].includes(cur);

  const reviewSetPrepared =
    done.has("selections_saved") ||
    cur === "selections_saved" ||
    cur === "letters_generated" ||
    (done.has("findings_ready") && Boolean(progress.gates?.mayUseDisputeFlow));

  const strategyStepActive =
    cur === "selections_saved" || cur === "letters_generated" || done.has("selections_saved");

  return {
    enrolled: true,
    reportAnalyzed,
    reviewSetPrepared,
    strategyStepActive,
  };
}

export function buildOrionCaseStrip(ctx: OrionCaseStripContext): OrionCaseStripItem[] {
  const items: { key: keyof OrionCaseStripContext; label: string }[] = [
    { key: "enrolled", label: "Enrolled" },
    { key: "reportAnalyzed", label: "Report analyzed" },
    { key: "reviewSetPrepared", label: "Review set prepared" },
    { key: "strategyStepActive", label: "Strategy pending" },
  ];

  const flags = items.map((x) => Boolean(ctx[x.key]));
  const firstIncomplete = flags.findIndex((f) => !f);

  return items.map((item, i) => {
    let tone: OrionCaseStripTone;
    if (firstIncomplete === -1) {
      tone = i === items.length - 1 ? "current" : "complete";
    } else if (i < firstIncomplete) tone = "complete";
    else if (i === firstIncomplete) tone = "current";
    else tone = "upcoming";
    return { id: String(item.key), label: item.label, tone };
  });
}
