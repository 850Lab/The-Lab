import { describe, expect, it } from "vitest";
import {
  buildConfidenceMessage,
  buildNarrativeInputForConfirmation,
  buildNarrativeInputForStrategyPage,
  buildOutcomeExpectation,
  buildPriorityInsights,
  buildSituationSummary,
  type NarrativeInput,
} from "./narrativeBuilder";
import type { DisputeStrategyBundle } from "./strategyTypes";
import type { WorkflowEnvelope } from "./workflowTypes";

const emptyWorkflow = { userMessage: null } as unknown as WorkflowEnvelope;

function baseInput(over: Partial<NarrativeInput> = {}): NarrativeInput {
  return {
    program: null,
    reviewClaimsCount: 0,
    strongSuggestedCount: 0,
    totalAccountsExtracted: null,
    priorityCandidates: [],
    responseTotal: 0,
    escalationRecommendedCount: 0,
    mailedBureauCount: 0,
    letterRowCount: 0,
    roundNumber: null,
    analysisPending: false,
    ...over,
  };
}

describe("buildSituationSummary", () => {
  it("early / upload with no claims", () => {
    const t = buildSituationSummary(
      baseInput({
        program: {
          currentStep: "upload",
          isComplete: false,
          nextBestAction: null as never,
          progress: { current: 0, total: 1, completedSteps: [], upcomingSteps: [] },
        },
        reviewClaimsCount: 0,
      }),
    );
    expect(t).toMatch(/Add your report/i);
  });

  it("after analysis with items and strong opportunities", () => {
    const t = buildSituationSummary(
      baseInput({
        program: {
          currentStep: "review_claims",
          isComplete: false,
          nextBestAction: null as never,
          progress: { current: 1, total: 4, completedSteps: ["parse_analyze"], upcomingSteps: [] },
        },
        reviewClaimsCount: 6,
        strongSuggestedCount: 3,
        totalAccountsExtracted: 12,
      }),
    );
    expect(t).toMatch(/6 item/);
    expect(t).toMatch(/3/);
  });

  it("parse in progress", () => {
    const t = buildSituationSummary(
      baseInput({ analysisPending: true, program: { currentStep: "parse_analyze" } as never }),
    );
    expect(t).toMatch(/still reviewing|analyz/i);
  });
});

describe("buildPriorityInsights", () => {
  it("picks from strategy-style candidates and caps at 3", () => {
    const items = buildPriorityInsights(
      baseInput({
        priorityCandidates: [
          {
            key: "a",
            label: "Card A",
            why: "Short",
            impactLevel: "low",
            confidenceLevel: "low",
            inSuggestedRound: true,
          },
          {
            key: "b",
            label: "Card B",
            why: "Better",
            impactLevel: "high",
            confidenceLevel: "high",
            inSuggestedRound: true,
          },
        ],
        program: { currentStep: "select_disputes" } as never,
      }),
    );
    expect(items.length).toBeLessThanOrEqual(3);
    expect(items.some((l) => l.includes("Card B"))).toBe(true);
  });
});

describe("buildOutcomeExpectation", () => {
  it("mail step mentions realistic timing when sends exist", () => {
    const t = buildOutcomeExpectation(
      baseInput({ mailedBureauCount: 1, program: { currentStep: "mail" } as never }),
    );
    expect(t).toMatch(/week|track/i);
  });
});

describe("buildConfidenceMessage", () => {
  it("reflects many strong-suggested items", () => {
    const t = buildConfidenceMessage(
      baseInput({ reviewClaimsCount: 4, strongSuggestedCount: 2 }),
    );
    expect(t.length).toBeGreaterThan(20);
  });
});

describe("adapters", () => {
  it("buildNarrativeInputForStrategyPage uses dispute payload", () => {
    const bundle: DisputeStrategyBundle = {
      workflow: emptyWorkflow,
      selectionAllowed: true,
      selectionBlockedReason: null,
      disputeStrategy: {
        roundNumber: 1,
        eligibleCount: 2,
        groups: [
          {
            reviewType: "x",
            items: [
              {
                review_claim_id: "c1",
                review_type: "x",
                summary: "",
                question: "",
                entities: {},
                recommendation: {
                  id: "c1",
                  accountName: "Ex Bank",
                  issueType: "",
                  impactLevel: "high" as const,
                  confidence: { level: "high" as const, score: 0.9 },
                  why: { short: "Inconsistent", detailed: "d" },
                  recommended: true,
                  optional: false,
                  summary: "",
                },
              },
            ],
          },
        ],
        eligibleReviewClaimIds: ["c1"],
        defaultSelectedReviewClaimIds: [],
        suggestedReviewClaimIds: ["c1"],
        deterministic: null,
        constraints: {
          isAdmin: false,
          usingFreeMode: false,
          freePerBureauLimit: 0,
          lettersBalance: 0,
          hasUsedFreeLetters: false,
        },
      },
    };
    const input = buildNarrativeInputForStrategyPage(
      { currentStep: "select_disputes", isComplete: false } as never,
      bundle,
    );
    expect(input.reviewClaimsCount).toBeGreaterThan(0);
    expect(input.priorityCandidates.length).toBe(1);
  });

  it("buildNarrativeInputForConfirmation", () => {
    const n = buildNarrativeInputForConfirmation({ currentStep: "review_claims" } as never, 3, 10, false);
    expect(n.reviewClaimsCount).toBe(3);
    expect(n.totalAccountsExtracted).toBe(10);
  });
});
