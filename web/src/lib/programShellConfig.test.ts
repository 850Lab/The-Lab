import { describe, expect, it } from "vitest";
import {
  currentTimelineIndex,
  isStructuredReportPath,
  programHeaderCopy,
  reportEntryHref,
} from "./programShellConfig";
import type { ProgramState } from "./programStateTypes";

function makeState(over: Partial<ProgramState>): ProgramState {
  return {
    version: "1",
    workflowId: "wf-1",
    currentStep: "upload",
    stepStatus: null,
    canonicalRoute: "/upload",
    allowedNavRoutes: ["/upload"],
    nextBestAction: {
      label: "Next",
      description: "",
      targetRoute: "/upload",
      required: false,
    },
    progress: {
      current: 0,
      total: 10,
      completedSteps: [],
      upcomingSteps: [],
    },
    blockingIssues: [],
    isComplete: false,
    ...over,
  };
}

describe("currentTimelineIndex", () => {
  it("uses backend currentStep for review on upload/analyze/prepare (not the URL’s column)", () => {
    const p = makeState({ currentStep: "review_claims" });
    expect(currentTimelineIndex(p, "/upload")).toBe(2);
    expect(currentTimelineIndex(p, "/analyze")).toBe(2);
    expect(currentTimelineIndex(p, "/prepare")).toBe(2);
  });

  it("ignores /report in the path and uses backend currentStep (secondary view)", () => {
    const p = makeState({ currentStep: "letter_generation" });
    expect(currentTimelineIndex(p, "/report")).toBe(5);
  });
});

describe("programHeaderCopy", () => {
  it("keeps /execute on Check-in framing without fighting page hero", () => {
    const p = makeState({ currentStep: "select_disputes" });
    const c = programHeaderCopy(p, "/execute");
    expect(c.stepLabel).toBe("Check-in");
  });
});

describe("reportEntryHref", () => {
  it("points to structured report when a program exists", () => {
    const h = reportEntryHref(makeState({ currentStep: "select_disputes" }), "/strategy");
    expect(h.to).toBe("/report");
    expect(h.label).toContain("report");
  });

  it("shows viewing on /report", () => {
    const h = reportEntryHref(makeState({ currentStep: "select_disputes" }), "/report");
    expect(h.to).toBe("/report");
    expect(h.label.toLowerCase()).toContain("viewing");
  });

  it("suggests upload for guests without a program", () => {
    const h = reportEntryHref(null, "/get-report");
    expect(h.to).toBe("/upload");
  });
});

describe("isStructuredReportPath", () => {
  it("detects the report route", () => {
    expect(isStructuredReportPath("/report")).toBe(true);
    expect(isStructuredReportPath("/report/extra")).toBe(false);
  });
});
