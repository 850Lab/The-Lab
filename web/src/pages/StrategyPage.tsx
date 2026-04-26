import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { NarrativeSummaryCard } from "@/components/NarrativeSummaryCard";
import { EscalationProgramSection } from "@/components/EscalationProgramSection";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { StrategyCTASection } from "@/components/StrategyCTASection";
import { StrategyNarrativeCard } from "@/components/StrategyNarrativeCard";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { labelForReviewType } from "@/lib/reviewClaimsDisplay";
import type { DisputeStrategyPayload, ReviewClaimWithRecommendation } from "@/lib/strategyTypes";
import {
  strategyConfidencePillClass,
  strategyConfidenceUserLabel,
} from "@/lib/strategyRecommendationUi";
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
  easeStep,
  stepChildVariants as headerVariants,
  stepPageVariants as pageVariants,
} from "@/lib/motionStep";
import { buildNarrativeInputForStrategyPage } from "@/lib/narrativeBuilder";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";
import { PresentationDetails } from "@/components/presentation/PresentationStepFrame";

const DRAFT_DEBOUNCE_MS = 650;

/** sessionStorage: user chose to see the full dispute list (Phase 6.5). */
const STRATEGY_LIST_SESSION_KEY = "850lab_strategy_v1_list";

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

function claimLine(c: ReviewClaimWithRecommendation): string {
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
    programState,
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
  const [selectionPhase, setSelectionPhase] = useState<"intro" | "list">(() => {
    if (typeof window === "undefined") return "list";
    return window.sessionStorage.getItem(STRATEGY_LIST_SESSION_KEY) === "1" ? "list" : "intro";
  });
  const [openStrategyGroup, setOpenStrategyGroup] = useState<string | null>(null);

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

  const tryToggle = (it: ReviewClaimWithRecommendation) => {
    const id = it.review_claim_id;
    setSelected((prev) => {
      const was = prev.has(id);
      if (was) {
        const r = it.recommendation;
        if (
          r?.recommended &&
          r.confidence.level === "high" &&
          !window.confirm(
            "This is one of your strongest dispute picks for this round. Are you sure you want to remove it?",
          )
        ) {
          return prev;
        }
        const next = new Set(prev);
        next.delete(id);
        scheduleDraftSave(next);
        return next;
      }
      const next = new Set(prev);
      next.add(id);
      scheduleDraftSave(next);
      return next;
    });
  };

  const strategy = bundle?.disputeStrategy;

  useEffect(() => {
    if (!strategy?.groups?.length) {
      setOpenStrategyGroup(null);
      return;
    }
    setOpenStrategyGroup((prev) => {
      if (prev != null && strategy.groups.some((x) => x.reviewType === prev)) return prev;
      return strategy.groups[0]!.reviewType;
    });
  }, [strategy]);

  const systemRecommendedIds = useMemo(
    () => new Set(strategy?.suggestedReviewClaimIds ?? []),
    [strategy?.suggestedReviewClaimIds],
  );

  const themesText = useMemo(() => {
    if (!strategy?.groups?.length) return "your reviewed credit items";
    const labels = strategy.groups.map((g) => labelForReviewType(g.reviewType));
    return labels.slice(0, 5).join(", ");
  }, [strategy?.groups]);

  const startHere = useMemo(
    () => (strategy ? buildStartHereSummary(strategy, systemRecommendedIds) : null),
    [strategy, systemRecommendedIds],
  );

  const strategyNarrativeInput = useMemo(
    () => (bundle ? buildNarrativeInputForStrategyPage(programState, bundle) : null),
    [programState, bundle],
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

  const showSelectionIntro =
    !loading &&
    !!bundle?.selectionAllowed &&
    !!strategy &&
    strategy.eligibleCount > 0 &&
    selectionPhase === "intro";
  const showSelectionList =
    !loading &&
    !!bundle?.selectionAllowed &&
    !!strategy &&
    strategy.eligibleCount > 0 &&
    selectionPhase === "list";

  return (
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn
        className={`relative z-10 mx-auto max-w-xl px-4 pb-24 sm:max-w-2xl sm:px-6 sm:pb-28 ${stepMainColumnTopClass(!!workflowId)}`}
      >
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          <AnimatePresence mode="wait">
            {showSelectionIntro && startHere ? (
              <motion.div
                key="strategy-intro"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.32, ease: easeStep }}
                className="mx-auto max-w-lg"
              >
                {strategy && strategy.roundNumber > 1 ? (
                  <p className="mx-auto mb-2 max-w-md text-center text-xs font-semibold uppercase tracking-[0.14em] text-lab-subtle">
                    Dispute round {strategy.roundNumber} · same program
                  </p>
                ) : null}
                <h2 className="step-title">We found your strongest opportunities</h2>
                <p className="step-support">
                  {startHere.recommendedCount} recommended
                  {startHere.optionalCount > 0
                    ? `, ${startHere.optionalCount} optional`
                    : ""}
                </p>
                <div className="mt-8 flex justify-center gap-10 rounded-2xl border border-white/[0.1] bg-lab-surface/80 px-6 py-10 shadow-[0_20px_50px_-32px_rgba(0,0,0,0.55)] sm:gap-14 sm:px-8">
                  <div className="text-center">
                    <p
                      className="font-heading text-4xl font-bold tabular-nums text-lab-text sm:text-5xl"
                      aria-live="polite"
                    >
                      {startHere.recommendedCount}
                    </p>
                    <p className="mt-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-subtle">
                      Recommended
                    </p>
                  </div>
                  <div className="w-px shrink-0 bg-white/[0.1]" aria-hidden />
                  <div className="text-center">
                    <p
                      className="font-heading text-4xl font-bold tabular-nums text-lab-muted sm:text-5xl"
                      aria-live="polite"
                    >
                      {startHere.optionalCount}
                    </p>
                    <p className="mt-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-subtle">
                      Optional
                    </p>
                  </div>
                </div>
                <div className="mt-10">
                  <button
                    type="button"
                    onClick={() => {
                      try {
                        window.sessionStorage.setItem(STRATEGY_LIST_SESSION_KEY, "1");
                      } catch {
                        /* ignore */
                      }
                      setSelectionPhase("list");
                    }}
                    className="btn-primary-step w-full"
                  >
                    Review recommended disputes
                  </button>
                </div>
                <PresentationDetails label="View details" className="mt-4">
                  <p className="text-lab-text">
                    You&apos;re choosing what goes into this round—not inventing a strategy from
                    scratch. The list step locks your package, then payment and letter generation
                    use these selections.
                  </p>
                  <ul className="mt-3 list-disc space-y-1.5 pl-4 text-sm">
                    <li>Start with the highest-priority items.</li>
                    <li>Your letters are built from what you confirm here.</li>
                    <li>Same path: select → pay or credits → letters.</li>
                  </ul>
                </PresentationDetails>
              </motion.div>
            ) : (
              <motion.div
                key="strategy-hero"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.28, ease: easeStep }}
              >
                <motion.h2
                  variants={headerVariants}
                  className="step-title"
                >
                  {strategyHero.title}
                </motion.h2>

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

                {showSelectionList ? (
                  <PresentationDetails label="Why this step matters" className="mt-5">
                    <ul className="list-disc space-y-1.5 pl-4 text-sm">
                      <li>Focus on the highest-priority items first; add optional items only if they fit.</li>
                      <li>This step locks what goes into your dispute package—then payment, then letters.</li>
                    </ul>
                    <p className="mt-2 text-sm text-lab-subtle">
                      1) Review list · 2) Keep what belongs in this round · 3) Continue to payment
                      when ready.
                    </p>
                  </PresentationDetails>
                ) : null}
              </motion.div>
            )}
          </AnimatePresence>

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

          {showSelectionList ? (
            <>
              <div className="mt-5 space-y-4 sm:mt-6 sm:space-y-5">
                <PresentationDetails label="Opportunity summary">
                  {strategyNarrativeInput ? (
                    <div className="mb-4">
                      <NarrativeSummaryCard input={strategyNarrativeInput} variant="compact" />
                    </div>
                  ) : null}
                  {startHere ? (
                    <div className="space-y-2.5 text-sm leading-relaxed text-lab-muted sm:text-[15px]">
                      <p>
                        <span className="font-semibold text-lab-text">Best first-round items: </span>
                        {startHere.recommendedCount} lined up
                        {startHere.themesShort ? ` — ${startHere.themesShort}` : ""}.
                      </p>
                      <p>
                        <span className="font-semibold text-lab-text">Caution: </span>
                        {startHere.cautionAmongRecommended > 0
                          ? `${startHere.cautionAmongRecommended} recommended pick(s) in higher-impact categories.`
                          : "Still read each line before you continue."}
                      </p>
                      <p>
                        <span className="font-semibold text-lab-text">Optional: </span>
                        {startHere.optionalCount} add-on{startHere.optionalCount === 1 ? "" : "s"} you
                        can skip for now.
                      </p>
                    </div>
                  ) : null}
                  <div className="mt-4 border-t border-white/[0.06] pt-4">
                    <StrategyNarrativeCard strategy={strategy} themesText={themesText} />
                  </div>
                </PresentationDetails>
              </div>

              {bundle.escalationGuide?.programEscalation &&
              bundle.escalationGuide.programEscalation.groups.length > 0 ? (
                <motion.div variants={headerVariants} className="mt-6 sm:mt-7">
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

              <motion.div variants={headerVariants} className="mt-8 space-y-4 sm:mt-9 sm:space-y-5">
                {strategy.groups.map((g) => (
                  <details
                    key={g.reviewType}
                    open={openStrategyGroup === g.reviewType}
                    onToggle={(e) => {
                      if (e.currentTarget.open) {
                        setOpenStrategyGroup(g.reviewType);
                      } else {
                        setOpenStrategyGroup((x) => (x === g.reviewType ? null : x));
                      }
                    }}
                    className="group rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-3 sm:px-5 sm:py-4"
                  >
                    <summary className="flex cursor-pointer list-none items-baseline justify-between gap-2 marker:content-none [&::-webkit-details-marker]:hidden">
                      <h2 className="text-base font-semibold text-lab-text">
                        {labelForReviewType(g.reviewType)}
                      </h2>
                      <span className="flex items-center gap-2 text-sm tabular-nums text-lab-accent">
                        {g.items.length}
                        <span
                          className="text-lab-subtle transition-transform group-open:rotate-180"
                          aria-hidden
                        >
                          ▾
                        </span>
                      </span>
                    </summary>
                    <ul className="mt-3 space-y-3 border-t border-white/[0.06] pt-3">
                      {g.items.map((it) => {
                        const systemRec = systemRecommendedIds.has(it.review_claim_id);
                        const rec = it.recommendation;
                        const impact = selectionImpactForReviewType(
                          g.reviewType,
                          systemRec,
                        );
                        const headline = rec?.summary?.trim() || claimLine(it);
                        const oneLine = rec?.why?.short;
                        const forThisRound = rec ? rec.recommended : systemRec;
                        return (
                          <li key={it.review_claim_id}>
                            <label className="flex cursor-pointer gap-3 rounded-lg px-1 py-2 transition-colors hover:bg-white/[0.04]">
                              <input
                                type="checkbox"
                                className="mt-1.5 h-4 w-4 shrink-0 rounded border-white/20 bg-lab-bg text-lab-accent focus:ring-lab-accent/40"
                                checked={selected.has(it.review_claim_id)}
                                onChange={() => tryToggle(it)}
                              />
                              <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                                {rec ? (
                                  <p className="text-[10px] font-medium uppercase tracking-wide text-lab-subtle">
                                    {rec.accountName}
                                    {rec.issueType ? (
                                      <span className="text-lab-subtle/80">
                                        {" "}
                                        · {rec.issueType}
                                      </span>
                                    ) : null}
                                  </p>
                                ) : null}
                                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                                  <div className="min-w-0">
                                    <p className="text-sm font-medium leading-snug text-lab-text">
                                      {headline}
                                    </p>
                                    {oneLine ? (
                                      <p className="mt-1 text-sm leading-relaxed text-lab-muted">
                                        {oneLine}
                                      </p>
                                    ) : null}
                                  </div>
                                  <div className="flex shrink-0 flex-col items-start gap-1.5 sm:items-end">
                                    {rec ? (
                                      <span
                                        className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${strategyConfidencePillClass(
                                          rec.confidence.level,
                                        )}`}
                                        title={
                                          rec.confidence.score != null
                                            ? `Strength score ${(rec.confidence.score * 100).toFixed(0)}%`
                                            : undefined
                                        }
                                      >
                                        {strategyConfidenceUserLabel(rec.confidence.level)}
                                      </span>
                                    ) : null}
                                    {forThisRound ? (
                                      <span className="rounded-md bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-200/90">
                                        For this round
                                      </span>
                                    ) : (
                                      <span className="rounded-md bg-white/[0.06] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
                                        Optional add-on
                                      </span>
                                    )}
                                  </div>
                                </div>
                                {rec ? (
                                  <details className="details-calm group mt-0.5 rounded-md border border-white/[0.05] bg-black/15">
                                    <summary className="cursor-pointer list-none px-2 py-1.5 text-[11px] font-medium text-lab-muted marker:content-none [&::-webkit-details-marker]:hidden hover:text-lab-text">
                                      <span className="underline decoration-white/10 underline-offset-2 group-open:text-lab-accent">
                                        More context (optional)
                                      </span>
                                    </summary>
                                    <div className="space-y-2 border-t border-white/[0.06] px-2 py-2 text-[11px] leading-relaxed text-lab-subtle sm:text-xs">
                                      {rec.why?.detailed && rec.why.detailed !== oneLine ? (
                                        <p>{rec.why.detailed}</p>
                                      ) : null}
                                      <p>
                                        <span className="font-medium text-lab-muted">If checked: </span>
                                        {impact.ifSelected}
                                      </p>
                                      <p>
                                        <span className="font-medium text-lab-muted">If unchecked: </span>
                                        {impact.ifOmitted}
                                      </p>
                                    </div>
                                  </details>
                                ) : (
                                  <details className="details-calm group mt-0.5 rounded-md border border-white/[0.05] bg-black/15">
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
                                )}
                              </span>
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  </details>
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
