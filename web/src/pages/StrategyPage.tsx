import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { EscalationProgramSection } from "@/components/EscalationProgramSection";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { StrategyCTASection } from "@/components/StrategyCTASection";
import { StrategyNarrativeCard } from "@/components/StrategyNarrativeCard";
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
import { selectionImpactForReviewType } from "@/lib/intelligenceExpression";

const DRAFT_DEBOUNCE_MS = 650;

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.09, delayChildren: 0.05 },
  },
};

const headerVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

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

export function StrategyPage() {
  const navigate = useNavigate();
  const {
    token,
    workflowId,
    authoritativeStepId,
    canonicalCustomerPath,
    applyWorkflowEnvelope,
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
      draftTimerRef.current = setTimeout(() => {
        draftTimerRef.current = null;
        const list = [...ids];
        void putDisputeSelectionDraft(token, workflowId, list).catch(() => {
          /* non-fatal; user can still confirm */
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

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[28%] z-0 h-[min(58vw,400px)] w-[min(58vw,400px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.07] blur-[96px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-xl px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          <motion.p
            variants={headerVariants}
            className="text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-accent"
          >
            Your program · Strategy
          </motion.p>

          <motion.h1
            variants={headerVariants}
            className="mt-2 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-3xl"
          >
            We&apos;ve determined the best approach for this round
          </motion.h1>

          {!loading && strategy && strategy.roundNumber > 1 ? (
            <motion.p
              variants={headerVariants}
              className="mx-auto mt-2 max-w-md text-center text-xs font-semibold uppercase tracking-[0.14em] text-lab-accent/90"
            >
              Dispute round {strategy.roundNumber} · same program
            </motion.p>
          ) : null}

          <motion.p
            variants={headerVariants}
            className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            The system already ranked and filtered what&apos;s worth challenging — you&apos;re
            confirming the set, not exploring options from scratch. Adjust checkboxes if something
            shouldn&apos;t go this round. Next beat: only when this plan is locked — letter credits if
            you need them, then{" "}
            <strong className="font-medium text-lab-text">we generate your dispute letters</strong>{" "}
            from this plan.
          </motion.p>

          {!loading && bundle?.selectionAllowed && strategy && strategy.eligibleCount > 0 ? (
            <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-md">
              <ProgramFlowBridge>
                <span className="font-medium text-lab-text">Now we&apos;ve prepared your dispute list</span>{" "}
                from findings and review. This screen locks what gets challenged — then payment (or
                credits), then letters. Still one continuous path.
              </ProgramFlowBridge>
            </motion.div>
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
                className="inline-block font-semibold text-lab-accent hover:text-sky-300"
              >
                Go to your current step →
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
                className="inline-block font-semibold text-lab-accent hover:text-sky-300"
              >
                Go to your current step →
              </Link>
            </motion.div>
          ) : null}

          {!loading && bundle?.selectionAllowed && strategy && strategy.eligibleCount > 0 ? (
            <>
              <motion.div
                variants={headerVariants}
                className="mt-8 rounded-xl border border-white/[0.1] bg-lab-surface/70 px-4 py-3.5 text-center text-sm leading-relaxed text-lab-muted"
              >
                <span className="font-medium text-lab-text">Recommended for you:</span> items marked
                below match the system&apos;s starting set for this round. Uncheck what you don&apos;t
                want challenged; add others if you prefer.
              </motion.div>

              <motion.div variants={headerVariants} className="mt-6">
                <StrategyNarrativeCard strategy={strategy} themesText={themesText} />
              </motion.div>

              {bundle.escalationGuide?.programEscalation &&
              bundle.escalationGuide.programEscalation.groups.length > 0 ? (
                <motion.div variants={headerVariants} className="mt-6">
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
                className="mt-4 rounded-xl border border-white/[0.08] bg-lab-surface/90 px-4 py-3 text-center text-xs text-lab-muted sm:text-sm"
              >
                <span className="font-medium text-lab-text">{selectedCount}</span> selected ·{" "}
                <span className="font-medium text-lab-text">{bureauCount}</span> bureau
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
              </motion.div>

              <motion.div variants={headerVariants} className="mt-8 space-y-8">
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
                    <ul className="mt-3 space-y-2">
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
                              <span className="flex min-w-0 flex-1 flex-col gap-2 sm:gap-2">
                                <span className="flex flex-col gap-1.5 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
                                  <span className="text-sm leading-relaxed text-lab-text/90">
                                    {claimLine(it)}
                                  </span>
                                  {rec ? (
                                    <span className="shrink-0 self-start rounded-md bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-200/90">
                                      Stronger starting pick
                                    </span>
                                  ) : (
                                    <span className="shrink-0 self-start rounded-md bg-white/[0.06] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
                                      Optional add-on
                                    </span>
                                  )}
                                </span>
                                <div className="border-l border-lab-accent/25 pl-3 text-[11px] leading-relaxed text-lab-subtle sm:text-xs">
                                  <p>
                                    <span className="font-medium text-lab-muted">If selected: </span>
                                    {impact.ifSelected}
                                  </p>
                                  <p className="mt-1">
                                    <span className="font-medium text-lab-muted">If not selected: </span>
                                    {impact.ifOmitted}
                                  </p>
                                </div>
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

              <motion.div variants={headerVariants} className="mx-auto mt-8 max-w-md">
                <ProgramFlowBridge>
                  <span className="font-medium text-lab-text">Next:</span> lock this plan — the next
                  screen is the letter step, with checkout only if you still need credits. One primary
                  button below.
                </ProgramFlowBridge>
              </motion.div>

              <motion.div variants={headerVariants} className="mt-10 sm:mt-12">
                <StrategyCTASection
                  onStart={() => void handleContinue()}
                  disabled={!canContinue}
                  label={submitting ? "Saving…" : "Lock in plan & continue"}
                  hint="Locking in is the handoff to real letter output. If you already have letter credits, you skip straight to generation; otherwise you complete purchase once, then we generate bureau-ready text from this exact plan."
                />
              </motion.div>
            </>
          ) : null}
        </motion.div>
      </main>
    </div>
  );
}
