import type { IntakeSummaryBundle } from "@/lib/intakeTypes";
import type { ProgramState } from "@/lib/programStateTypes";
import type { WorkflowResponseMetricsResponse } from "@/lib/responseTypes";
import type { LettersContextResponse } from "@/lib/letterTypes";
import type { MailContextResponse } from "@/lib/mailTypes";
import type { DisputeStrategyBundle, DisputeStrategyPayload } from "@/lib/strategyTypes";

/**
 * Deterministic input for Phase 5 narrative (no new APIs, no LLM).
 * Callers pass only what they already have from ProgramState, intake, strategy, metrics, etc.
 */
export type NarrativePriorityItem = {
  key: string;
  label: string;
  why: string;
  impactLevel: "high" | "medium" | "low";
  confidenceLevel: "high" | "medium" | "low";
  inSuggestedRound: boolean;
};

export type NarrativeInput = {
  program: Pick<ProgramState, "currentStep" | "isComplete" | "nextBestAction" | "progress"> | null;
  /** Intake: total review claims (items surfaced for review) */
  reviewClaimsCount: number;
  /**
   * Count of suggested-round items with high confidence (from strategy recommendations).
   * 0 is fine when unknown.
   */
  strongSuggestedCount: number;
  totalAccountsExtracted: number | null;
  /** Top candidates for "priority insights" (caller may cap length) */
  priorityCandidates: NarrativePriorityItem[];
  responseTotal: number;
  escalationRecommendedCount: number;
  mailedBureauCount: number;
  letterRowCount: number;
  /** Dispute round from strategy, if known */
  roundNumber: number | null;
  /** Intake: parse not finished yet (optional override) */
  analysisPending?: boolean;
};

const IMP = { high: 3, medium: 2, low: 1 } as const;
const CONF = { high: 3, medium: 2, low: 1 } as const;

function stepRank(s: string | null): number {
  const order: string[] = [
    "upload",
    "parse_analyze",
    "review_claims",
    "select_disputes",
    "payment",
    "letter_generation",
    "proof_attachment",
    "mail",
    "track",
  ];
  const i = s ? order.indexOf(s) : -1;
  return i < 0 ? 99 : i;
}

function scoreP(item: NarrativePriorityItem): number {
  const sug = item.inSuggestedRound ? 100 : 0;
  return sug + IMP[item.impactLevel] * 10 + CONF[item.confidenceLevel] + 0.01;
}

/**
 * 1–2 short sentences, plain language.
 */
export function buildSituationSummary(d: NarrativeInput): string {
  const step = d.program?.currentStep ?? null;
  const done = d.program?.isComplete ?? false;

  if (done) {
    return "This guided round of your program is complete. The summary still reflects what we found and what you did along the way.";
  }

  if (d.analysisPending || step === "parse_analyze") {
    return "We’re still reviewing your file. A clear picture of what to work on will show as soon as analysis is ready.";
  }

  if (step === "upload" && d.reviewClaimsCount === 0) {
    return "Add your report when you’re ready. We’ll use it to spot what to focus on in this program.";
  }

  const n = d.reviewClaimsCount;
  const s = d.strongSuggestedCount;
  if (n <= 0) {
    if (stepRank(step) < stepRank("select_disputes")) {
      return "Your program is open—next steps on your path will add detail here as the system processes your file.";
    }
    return "There aren’t any review items in view yet. Follow your current program step; more detail can appear as things update.";
  }

  const accounts = d.totalAccountsExtracted;
  const aPart =
    accounts != null && accounts > 0
      ? ` We saw about ${accounts} account${accounts === 1 ? "" : "s"} worth scanning for issues.`
      : "";

  if (s > 0) {
    const core = `We found ${n} item${n === 1 ? "" : "s"} on your report, with ${s} of ${
      s === 1 ? "them" : "them"
    } looking like ${s === 1 ? "a clear opportunity" : "strong opportunities"} to work on in this program.`;
    return aPart ? `${core}${aPart}`.replace(/\s+/g, " ").trim() : core;
  }

  const core = `We found ${n} item${n === 1 ? "" : "s"} on your report to review together.`;
  return aPart ? `${core}${aPart}`.replace(/\s+/g, " ").trim() : core;
}

const MAX_INSIGHTS = 3;
const CLIP = 200;

/**
 * 0–3 short human lines. Empty when we have no candidates (caller still may hide card sections).
 */
export function buildPriorityInsights(d: NarrativeInput): string[] {
  if (d.priorityCandidates.length === 0) {
    if (d.reviewClaimsCount > 0 && d.program?.currentStep === "review_claims") {
      return [
        "Work through the list in front of you—removing a line is fine if it’s not a fit. What stays is what the next step will use to build this round.",
      ];
    }
    if (d.program?.currentStep === "select_disputes" && d.strongSuggestedCount > 0) {
      return [
        `The program has pre-selected about ${d.strongSuggestedCount} of the higher-signal item${d.strongSuggestedCount === 1 ? "" : "s"} for this round—you can still adjust with checkboxes.`,
      ];
    }
    return [];
  }
  const sorted = [...d.priorityCandidates].sort((a, b) => scoreP(b) - scoreP(a));
  const out: string[] = [];
  for (const p of sorted) {
    if (out.length >= MAX_INSIGHTS) break;
    const why = (p.why || p.label).trim();
    const clipped = why.length > CLIP ? why.slice(0, CLIP).replace(/\s+\S*$/, "…") : why;
    const when = p.inSuggestedRound
      ? "slated for this round"
      : "available to consider, even if it’s not in the core set for this round";
    out.push(`${p.label} — ${clipped} This is one of your ${when}.`);
  }
  return out;
}

/**
 * One short paragraph, realistic — no promises.
 */
export function buildOutcomeExpectation(d: NarrativeInput): string {
  const step = d.program?.currentStep ?? null;
  const done = d.program?.isComplete ?? false;

  if (done) {
    return "What happens next in the real world depends on how each furnish responds. In this app, you can still track sends and add responses for your records.";
  }

  if (d.analysisPending || step === "parse_analyze") {
    return "Once the review is done, the program will show what it suggests you focus on first, then you confirm at your own pace.";
  }

  if (step === "upload") {
    return "After the file is in, we look for the mix of things that are worth addressing this round, without turning it into a giant task list.";
  }

  if (step === "review_claims") {
    return "Finishing this step means we’re not guessing in the next step: your dispute round will line up with what you decided to keep on the list.";
  }

  if (step === "select_disputes") {
    const r = d.roundNumber;
    return `This part of the program is about locking what’s in dispute round ${
      r && r > 0 ? r : "this"
    }. From there, payment (if your plan uses it), then letters, follow the same guided path.`;
  }

  if (step === "payment") {
    return "This step unlocks the work that your plan covers so the program can build your letter package. Nothing that happens in payment replaces your right to your own copy of what we generate.";
  }

  if (step === "letter_generation" || d.letterRowCount > 0) {
    return "Letters package what you confirmed. The goal is a clean package you can use with bureaus or others as your situation allows, then track what happens after they’re out the door.";
  }

  if (step === "proof_attachment") {
    return "When proof is on file, it supports what the mail or partner path needs. That keeps the paper trail aligned with what the letters say.";
  }

  if (step === "mail" || d.mailedBureauCount > 0) {
    return d.mailedBureauCount > 0
      ? "Sends are moving or sent. Bureaus often work on a multi-week window—so changes to what you see on a report can lag behind what the mailbox shows."
      : "Mailing (or a partner send) is how your dispute actually reaches the other side. After you send, tracking is where the program lines up the story.";
  }

  if (step === "track" || d.responseTotal > 0) {
    return d.responseTotal > 0
      ? "You have responses in the app now—use the Responses and Escalation areas when a reply means you need a next move."
      : "In tracking, the program keeps send status and what you’ve logged. When replies arrive, add them to Responses so the program stays in sync with real life.";
  }

  if (d.responseTotal > 0) {
    return "Logging responses keeps the program from drifting from what the bureaus actually said. It also helps the next follow-up, if you need it.";
  }

  return "Work one step at a time. Each part is there so you’re not doing everything in your head with no place to look.";
}

/**
 * One or two short sentences—supportive, tied to our signals.
 */
export function buildConfidenceMessage(d: NarrativeInput): string {
  if (d.program?.isComplete) {
    return "If you use what’s here as your paper trail, you’re already in better shape than winging it alone. Keep the habit of logging what comes back.";
  }

  if (d.analysisPending || d.program?.currentStep === "parse_analyze") {
    return "Hang tight—your report is still the source of truth; we just need a clean pass through the analysis step.";
  }

  if (d.reviewClaimsCount > 0 && d.strongSuggestedCount >= 2) {
    return "Several items line up with strong enough signals in your data that the program is comfortable nudging you toward them first. You still choose what to include.";
  }
  if (d.strongSuggestedCount === 1) {
    return "There is at least one high-signal item worth reading closely—it's one of the stronger pieces of the picture we saw.";
  }

  const hasHigh = d.priorityCandidates.some(
    (p) => p.confidenceLevel === "high" && p.inSuggestedRound,
  );
  if (hasHigh) {
    return "The recommendations in play here match some of the clearest patterns in your data—not every line item is a battle worth fighting at once.";
  }

  if (d.escalationRecommendedCount > 0) {
    return "A few of your follow-ups have signals that an escalation path might help. That doesn’t mean you have to do more today—just that the program will hold that door open if you need it.";
  }

  if (d.program?.currentStep === "review_claims" && d.reviewClaimsCount > 0) {
    return "You’re looking at a curated list, not a dump of the whole file—taking time here usually saves work later in the same round.";
  }

  if (d.program?.currentStep === "select_disputes" && d.priorityCandidates.length > 0) {
    return "You’re in the part of the program where a focused set beats trying to fix the whole file at once.";
  }

  if (d.mailedBureauCount > 0) {
    return "Sends you’ve made through the system are a better anchor than memory alone when something goes to dispute.";
  }

  return "You’re working this in order. The program is built so you can trust the next target line even when the report feels big.";
}

function priorityItemsFromStrategyPayload(payload: DisputeStrategyPayload | null): {
  items: NarrativePriorityItem[];
  strongSuggested: number;
  round: number | null;
} {
  if (!payload) {
    return { items: [], strongSuggested: 0, round: null };
  }
  const suggested = new Set(payload.suggestedReviewClaimIds ?? []);
  const items: NarrativePriorityItem[] = [];
  for (const g of payload.groups) {
    for (const it of g.items) {
      const r = it.recommendation;
      if (!r) continue;
      items.push({
        key: it.review_claim_id,
        label: r.accountName,
        why: r.why?.short || it.summary || "",
        impactLevel: r.impactLevel,
        confidenceLevel: r.confidence.level,
        inSuggestedRound: suggested.has(it.review_claim_id),
      });
    }
  }
  const strongSuggested = items.filter(
    (x) => x.inSuggestedRound && x.confidenceLevel === "high",
  ).length;
  return { items, strongSuggested, round: payload.roundNumber };
}

function programSlice(
  programState: ProgramState | null,
): NarrativeInput["program"] {
  if (!programState) return null;
  return {
    currentStep: programState.currentStep,
    isComplete: programState.isComplete,
    nextBestAction: programState.nextBestAction,
    progress: programState.progress,
  };
}

export function buildNarrativeInputForStructuredReport(
  programState: ProgramState | null,
  intake: IntakeSummaryBundle | null,
  strategyBundle: DisputeStrategyBundle | null,
  responseMetrics: WorkflowResponseMetricsResponse | null,
  mail: MailContextResponse | null,
  letters: LettersContextResponse | null,
  analysisPending: boolean,
): NarrativeInput {
  const { items, strongSuggested, round } = priorityItemsFromStrategyPayload(
    strategyBundle?.disputeStrategy ?? null,
  );
  const claims =
    intake?.intake.reviewClaimsCount ?? intake?.intake.reviewClaims.length ?? 0;
  return {
    program: programSlice(programState),
    reviewClaimsCount: claims,
    strongSuggestedCount: strongSuggested,
    totalAccountsExtracted: intake?.intake.aggregates?.totalAccountsExtracted ?? null,
    priorityCandidates: items,
    responseTotal: responseMetrics?.metrics.totalResponses ?? 0,
    escalationRecommendedCount: responseMetrics?.metrics.escalationRecommendedCount ?? 0,
    mailedBureauCount: mail?.mail.mailedCount ?? 0,
    letterRowCount: letters?.letters.length ?? 0,
    roundNumber: round,
    analysisPending,
  };
}

export function buildNarrativeInputForStrategyPage(
  programState: ProgramState | null,
  bundle: DisputeStrategyBundle,
): NarrativeInput {
  const p = bundle.disputeStrategy;
  const { items, strongSuggested, round } = priorityItemsFromStrategyPayload(p);
  let claimN = 0;
  if (p) {
    for (const g of p.groups) {
      claimN += g.items.length;
    }
    if (claimN === 0) {
      claimN = p.eligibleCount;
    }
  }
  return {
    program: programSlice(programState),
    reviewClaimsCount: claimN,
    strongSuggestedCount: strongSuggested,
    totalAccountsExtracted: null,
    priorityCandidates: items,
    responseTotal: 0,
    escalationRecommendedCount: 0,
    mailedBureauCount: 0,
    letterRowCount: 0,
    roundNumber: round,
    analysisPending: false,
  };
}

export function buildNarrativeInputForConfirmation(
  programState: ProgramState | null,
  reviewClaimsCount: number,
  totalAccountsExtracted: number | null,
  analysisPending: boolean,
): NarrativeInput {
  return {
    program: programSlice(programState),
    reviewClaimsCount,
    strongSuggestedCount: 0,
    totalAccountsExtracted,
    priorityCandidates: [],
    responseTotal: 0,
    escalationRecommendedCount: 0,
    mailedBureauCount: 0,
    letterRowCount: 0,
    roundNumber: null,
    analysisPending,
  };
}
