import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { EscalationProgramSection } from "@/components/EscalationProgramSection";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { StrategyCTASection } from "@/components/StrategyCTASection";
import { StrategyNarrativeCard } from "@/components/StrategyNarrativeCard";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type { ReviewClaimJson } from "@/lib/intakeTypes";
import { labelForReviewType } from "@/lib/reviewClaimsDisplay";
import type { DisputeStrategyPayload } from "@/lib/strategyTypes";
import {
  fetchDisputeStrategy,
  postDisputeSelectionConfirm,
  putDisputeSelectionDraft,
} from "@/lib/workflowApi";
import { customerPathFromEnvelope } from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  orionStepHeroCopy,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import { selectionImpactForReviewType } from "@/lib/intelligenceExpression";
import {
  stepChildVariants as headerVariants,
  stepPageVariants as pageVariants,
} from "@/lib/motionStep";

const DRAFT_DEBOUNCE_MS = 650;

const STRATEGY_HERO_FALLBACK = {
  title: "Choose what to include in this round",
  subtitle:
    "We organized your strongest dispute opportunities for you. You do not need to challenge everything at once. Start with the items that make the most sense for this round.",
} as const;

const CAUTION_REVIEW_TYPES = new Set([
  "negative_impact",
  "unverifiable_information",
  "accuracy_verification",
]);

function claimLine(c: ReviewClaimJson): string {
  const s = c.summary?.trim() || c.question?.trim() || c.review_claim_id;
  const b = c.entities?.bureau;
  return b ? `${s} (${b})` : s;
}

function uniqueBureauCount(selectedIds: Set<string>, strategy: DisputeStrategyPayload): number {
  const b = new Set<string>();
  for (const g of strategy.groups) {
    for (const it of g.items) {
      if (!selectedIds.has(it.review_claim_id)) continue;
      const x = (it.entities?.bureau || "").trim().toLowerCase();
      if (x) b.add(x);
    }
  }
  return b.size;
}

function buildStartHereSummary(strategy: DisputeStrategyPayload, recommended: Set<string>) {
  let recommendedCount = 0;
  let optionalCount = 0;
  let cautionAmongRecommended = 0;
  const typeLabels = new Set<string>();

  for (const g of strategy.groups) {
    const cautionType = CAUTION_REVIEW_TYPES.has(g.reviewType);
    for (const it of g.items) {
      if (recommended.has(it.review_claim_id)) {
        recommendedCount++;
        typeLabels.add(labelForReviewType(g.reviewType));
        if (cautionType) cautionAmongRecommended++;
      } else {
        optionalCount++;
      }
    }
  }

  const labelsArr = [...typeLabels];
  const themesShort =
    labelsArr.length > 4
      ? `${labelsArr.slice(0, 4).join(" · ")}…`
      : labelsArr.join(" · ") || "your report";

  return {
    recommendedCount,
    optionalCount,
    cautionAmongRecommended,
    themesShort,
  };
}

export function StrategyPage() {
  const navigate = useNavigate();
  const {
    token,
    workflowId,
    authoritativeStepId,
    canonicalCustomerPath,
    applyWorkflowEnvelope,
    orionViewModel,
    integrityHints,
  } = useCustomerWorkflow();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [bundle, setBundle] = useState<Awaited<ReturnType<typeof fetchDisputeStrategy>> | null>(
    null,
  );
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const draftTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const draftGenerationRef = useRef(0);
  const [draftStatus, setDraftStatus] = useState<"idle" | "saving" | "saved">("idle");

  const load = useCallback(async () => {
    if (!token || !workflowId) {
      setBundle(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const b = await fetchDisputeStrategy(token, workflowId);
      setBundle(b);
      applyWorkflowEnvelope(b.workflow);
      const ds = b.disputeStrategy;
      if (ds?.defaultSelectedReviewClaimIds?.length) {
        setSelected(new Set(ds.defaultSelectedReviewClaimIds));
      } else {
        setSelected(new Set());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBundle(null);
    } finally {
      setLoading(false);
    }
  }, [token, workflowId, applyWorkflowEnvelope]);

  useEffect(() => {
    void load();
  }, [load]);

  const scheduleDraftSave = useCallback(
    (ids: Set<string>) => {
      if (!token || !workflowId || !bundle?.selectionAllowed) return;
      if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
      const gen = ++draftGenerationRef.current;
      draftTimerRef.current = setTimeout(() => {
        draftTimerRef.current = null;
        const list = [...ids];
        setDraftStatus("saving");
        void putDisputeSelectionDraft(token, workflowId, list)
          .then(() => {
            if (gen !== draftGenerationRef.current) return;
            setDraftStatus("saved");
            window.setTimeout(() => {
              setDraftStatus((s) => (s === "saved" ? "idle" : s));
            }, 2200);
          })
          .catch(() => {
            if (gen !== draftGenerationRef.current) return;
            setDraftStatus("idle");
          });
      }, DRAFT_DEBOUNCE_MS);
    },
    [token, workflowId, bundle?.selectionAllowed],
  );

  useEffect(
    () => () => {
      if (draftTimerRef.current) clearTimeout(draftTimerRef.current);
    },
    [],
  );

  const toggleId = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      scheduleDraftSave(next);
      return next;
    });
  };

  const strategy = bundle?.disputeStrategy;

  const recommendedIds = useMemo(
    () => new Set(strategy?.defaultSelectedReviewClaimIds ?? []),
    [strategy?.defaultSelectedReviewClaimIds],
  );

  const themesText = useMemo(() => {
    if (!strategy?.groups?.length) return "your reviewed credit items";
    const labels = strategy.groups.map((g) => labelForReviewType(g.reviewType));
    return labels.slice(0, 5).join(", ");
  }, [strategy?.groups]);

  const startHere = useMemo(
    () => (strategy ? buildStartHereSummary(strategy, recommendedIds) : null),
    [strategy, recommendedIds],
  );

  const selectedCount = selected.size;
  const bureauCount = strategy ? uniqueBureauCount(selected, strategy) : 0;
  const canContinue =
    !!token &&
    !!workflowId &&
    bundle?.selectionAllowed &&
    authoritativeStepId === "select_disputes" &&
    selectedCount > 0 &&
    !submitting &&
    !loading;

  const handleContinue = async () => {
    if (!token || !workflowId || !canContinue) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const r = await postDisputeSelectionConfirm(token, workflowId, [...selected]);
      applyWorkflowEnvelope(r.workflow);
      navigate(customerPathFromEnvelope(r.workflow), { replace: true });
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const orionAuthority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const strategyHero = useMemo(
    () => orionStepHeroCopy(orionAuthority, orionViewModel, STRATEGY_HERO_FALLBACK),
    [orionAuthority, orionViewModel],
  );

  return (
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn className="relative z-10 mx-auto max-w-xl px-4 pb-24 pt-24 sm:max-w-2xl sm:px-6 sm:pb-28 sm:pt-28">
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          <motion.p
            variants={headerVariants}
            className="step-eyebrow"
          >
            STEP 3 • BUILD YOUR DISPUTE ROUND
          </motion.p>

          <motion.h1
            variants={headerVariants}
            className="step-title"
          >
            {strategyHero.title}
          </motion.h1>

          {!loading && strategy && strategy.roundNumber > 1 ? (
            <motion.p
              variants={headerVariants}
              className="mx-auto mt-2 max-w-md text-center text-xs font-semibold uppercase tracking-[0.14em] text-lab-subtle"
            >
              Dispute round {strategy.roundNumber} · same program
            </motion.p>
          ) : null}

          <motion.p
            variants={headerVariants}
            className="step-support"
          >
            {strategyHero.subtitle}
          </motion.p>

          {!loading && bundle?.selectionAllowed && strategy && strategy.eligibleCount > 0 ? (
            <>
              <motion.div
                variants={headerVariants}
                className="surface-emerald-reassure mx-auto mt-6 max-w-lg"
              >
                <ul className="space-y-2 text-left text-sm leading-relaxed text-emerald-50/95 sm:text-[15px]">
                  <li className="flex gap-2">
                    <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                      •
                    </span>
                    <span>You can focus on the highest-priority items first</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                      •
                    </span>
                    <span>You are reviewing recommendations, not starting from scratch</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                      •
                    </span>
                    <span>Your letters will be built from what you confirm here</span>
                  </li>
                </ul>
              </motion.div>

              <motion.div
                variants={headerVariants}
                className="surface-where-fits mx-auto mt-6 max-w-2xl"
              >
                <p className="text-center text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
                  How to use this page
                </p>
                <ol className="mt-3 flex flex-col gap-2 text-sm sm:mt-4 sm:flex-row sm:justify-center sm:gap-3 sm:text-[13px]">
                  <li className="flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text">
                    <span className="text-lab-accent">1.</span>
                    <span className="ml-1.5">Review recommended items</span>
                  </li>
                  <li className="flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted">
                    <span className="text-lab-subtle">2.</span>
                    <span className="ml-1.5">Keep what belongs in this round</span>
                  </li>
                  <li className="flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted">
                    <span className="text-lab-subtle">3.</span>
                    <span className="ml-1.5">Continue to payment when ready</span>
                  </li>
                </ol>
              </motion.div>

              <motion.div variants={headerVariants} className="mx-auto mt-6 max-w-2xl">
                <ProgramFlowBridge>
                  <span className="font-medium text-lab-text">Same continuous path:</span> this step
                  locks what goes into your dispute package — then payment (or credits), then letters.
                  You&apos;re confirming a guided plan, not inventing strategy alone.
                </ProgramFlowBridge>
              </motion.div>
            </>
          ) : null}

          {loading ? (
            <motion.p variants={headerVariants} className="mt-10 text-center text-sm text-lab-muted">
              Loading your strategy for this round…
            </motion.p>
          ) : null}

          {error ? (
            <motion.p variants={headerVariants} className="mt-10 text-center text-sm text-red-300/90">
              {error}
            </motion.p>
          ) : null}

          {!loading && bundle && !bundle.selectionAllowed ? (
            <motion.div
              variants={headerVariants}
              className="mt-10 space-y-3 text-center text-sm text-lab-muted"
            >
              <p>
                {bundle.selectionBlockedReason ||
                  "Dispute selection isn’t available in your program right now."}
              </p>
              <Link
                to={canonicalCustomerPath}
                className="inline-block font-semibold text-lab-accent hover:text-zinc-100"
              >
                Continue in your program →
              </Link>
            </motion.div>
          ) : null}

          {!loading && bundle?.selectionAllowed && strategy && strategy.eligibleCount === 0 ? (
            <motion.div
              variants={headerVariants}
              className="mt-10 space-y-3 text-center text-sm text-lab-muted"
            >
              <p>
                No dispute-eligible items are available (high-confidence claims only). Continue from
                your current program step when it updates.
              </p>
              <Link
                to={canonicalCustomerPath}
                className="inline-block font-semibold text-lab-accent hover:text-zinc-100"
              >
                Continue in your program →
              </Link>
            </motion.div>
          ) : null}

          {!loading && bundle?.selectionAllowed && strategy && strategy.eligibleCount > 0 ? (
            <>
              {startHere ? (
                <motion.div
                  variants={headerVariants}
                  className="mt-8 rounded-xl border border-zinc-700/50 bg-gradient-to-b from-white/[0.04] to-lab-surface/60 px-4 py-4 sm:px-5 sm:py-5"
                >
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-lab-subtle">
                    Start here
                  </p>
                  <div className="mt-3 space-y-3 text-sm leading-relaxed text-lab-muted sm:text-[15px]">
                    <p>
                      <span className="font-semibold text-lab-text">Best first-round items: </span>
                      {startHere.recommendedCount} item
                      {startHere.recommendedCount === 1 ? "" : "s"} already lined up for you
                      {startHere.themesShort ? (
                        <>
                          {" "}
                          — themes include {startHere.themesShort}.
                        </>
                      ) : (
                        "."
                      )}{" "}
                      Not every box has to stay checked — focused rounds are often stronger.
                    </p>
                    <p>
                      <span className="font-semibold text-lab-text">Items that may need more caution: </span>
                      {startHere.cautionAmongRecommended > 0 ? (
                        <>
                          {startHere.cautionAmongRecommended} of your recommended picks sit in
                          higher-impact categories — worth a careful read before you continue.
                        </>
                      ) : (
                        <>Fewer high-tension categories in this starting set — still read each line.</>
                      )}
                    </p>
                    <p>
                      <span className="font-semibold text-lab-text">Fine to leave for later: </span>
                      {startHere.optionalCount} optional add-on
                      {startHere.optionalCount === 1 ? "" : "s"} you can skip for now — add only if
                      they fit this round.
                    </p>
                  </div>
                </motion.div>
              ) : null}

              <motion.div variants={headerVariants} className="mt-8">
                <StrategyNarrativeCard strategy={strategy} themesText={themesText} />
              </motion.div>

              {bundle.escalationGuide?.programEscalation &&
              bundle.escalationGuide.programEscalation.groups.length > 0 ? (
                <motion.div variants={headerVariants} className="mt-8">
                  <EscalationProgramSection
                    program={bundle.escalationGuide.programEscalation}
                    token={token!}
                    workflowId={workflowId!}
                    applyWorkflowEnvelope={applyWorkflowEnvelope}
                    onUpdated={() => void load()}
                  />
                </motion.div>
              ) : null}

              <motion.div
                variants={headerVariants}
                className="mt-6 flex flex-col items-center gap-1 rounded-xl border border-white/[0.08] bg-lab-surface/90 px-4 py-3 text-center sm:flex-row sm:justify-center sm:gap-3 sm:text-left"
              >
                <p className="text-xs text-lab-muted sm:text-sm">
                  <span className="font-semibold text-lab-text">{selectedCount}</span> selected ·{" "}
                  <span className="font-semibold text-lab-text">{bureauCount}</span> bureau
                  {bureauCount === 1 ? "" : "s"} covered
                  {strategy.constraints.usingFreeMode ? (
                    <>
                      {" "}
                      · Free plan: max {strategy.constraints.freePerBureauLimit} per bureau
                    </>
                  ) : null}
                  {!strategy.constraints.isAdmin ? (
                    <> · Letter credits: {strategy.constraints.lettersBalance}</>
                  ) : null}
                </p>
                {draftStatus === "saving" ? (
                  <span className="text-[11px] font-medium text-lab-accent sm:text-xs" role="status">
                    Updating your selections…
                  </span>
                ) : draftStatus === "saved" ? (
                  <span className="text-[11px] font-medium text-emerald-300/90 sm:text-xs" role="status">
                    Selections saved
                  </span>
                ) : (
                  <span className="text-[11px] text-lab-subtle sm:text-xs">Your current round is up to date</span>
                )}
              </motion.div>

              <motion.div variants={headerVariants} className="mt-10 space-y-8 sm:space-y-10">
                {strategy.groups.map((g) => (
                  <section
                    key={g.reviewType}
                    className="rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-4 sm:px-5 sm:py-5"
                  >
                    <div className="flex items-baseline justify-between gap-2 border-b border-white/[0.06] pb-3">
                      <h2 className="text-base font-semibold text-lab-text">
                        {labelForReviewType(g.reviewType)}
                      </h2>
                      <span className="text-sm tabular-nums text-lab-accent">{g.items.length}</span>
                    </div>
                    <ul className="mt-3 space-y-3">
                      {g.items.map((it) => {
                        const rec = recommendedIds.has(it.review_claim_id);
                        const impact = selectionImpactForReviewType(g.reviewType, rec);
                        return (
                          <li key={it.review_claim_id}>
                            <label className="flex cursor-pointer gap-3 rounded-lg px-1 py-2 transition-colors hover:bg-white/[0.04]">
                              <input
                                type="checkbox"
                                className="mt-1 h-4 w-4 shrink-0 rounded border-white/20 bg-lab-bg text-lab-accent focus:ring-lab-accent/40"
                                checked={selected.has(it.review_claim_id)}
                                onChange={() => toggleId(it.review_claim_id)}
                              />
                              <span className="flex min-w-0 flex-1 flex-col gap-2">
                                <span className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                                  <span className="text-sm leading-relaxed text-lab-text/90">
                                    {claimLine(it)}
                                  </span>
                                  {rec ? (
                                    <span className="shrink-0 self-start rounded-md bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-200/90">
                                      Recommended pick
                                    </span>
                                  ) : (
                                    <span className="shrink-0 self-start rounded-md bg-white/[0.06] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
                                      Optional add-on
                                    </span>
                                  )}
                                </span>
                                <details className="details-calm group rounded-md border border-white/[0.05] bg-black/15">
                                  <summary className="cursor-pointer list-none px-2 py-1.5 text-[11px] font-medium text-lab-muted marker:content-none [&::-webkit-details-marker]:hidden hover:text-lab-text">
                                    <span className="underline decoration-white/10 underline-offset-2 group-open:text-lab-accent">
                                      How this affects your selection
                                    </span>
                                  </summary>
                                  <div className="border-t border-white/[0.06] px-2 py-2 text-[11px] leading-relaxed text-lab-subtle sm:text-xs">
                                    <p>
                                      <span className="font-medium text-lab-muted">If checked: </span>
                                      {impact.ifSelected}
                                    </p>
                                    <p className="mt-1.5">
                                      <span className="font-medium text-lab-muted">If unchecked: </span>
                                      {impact.ifOmitted}
                                    </p>
                                  </div>
                                </details>
                              </span>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                ))}
              </motion.div>

              {authoritativeStepId && authoritativeStepId !== "select_disputes" ? (
                <p className="mt-8 text-center text-sm text-lab-muted">
                  Continue is available when your program is on the dispute-selection step.
                </p>
              ) : null}

              {submitError ? (
                <p className="mt-6 text-center text-sm text-red-300/90">{submitError}</p>
              ) : null}

              <motion.div variants={headerVariants} className="mx-auto mt-10 max-w-md">
                <ProgramFlowBridge>
                  <span className="font-medium text-lab-text">Next up:</span> payment or credits, then
                  letter generation — all from this same selection. You can still adjust before letters
                  are drafted if your program allows.
                </ProgramFlowBridge>
              </motion.div>

              <motion.div variants={headerVariants} className="mt-10 sm:mt-12">
                <StrategyCTASection
                  onStart={() => void handleContinue()}
                  disabled={!canContinue}
                  title="Ready to turn this selection into your dispute package?"
                  hint="Once you continue, we’ll use your confirmed selections to prepare the next step before letter generation."
                  label={submitting ? "Continuing…" : "Continue to payment"}
                  footnote="You can still review your selections before letters are created."
                />
              </motion.div>
            </>
          ) : null}
        </motion.div>
      </StepMainColumn>
    </div>
  );
}
