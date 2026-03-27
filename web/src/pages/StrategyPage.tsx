import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { StrategyCTASection } from "@/components/StrategyCTASection";
import { StrategySummaryCard } from "@/components/StrategySummaryCard";
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
            className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
          >
            Plan
          </motion.p>

          <motion.h1
            variants={headerVariants}
            className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-3xl"
          >
            Choose what to dispute
          </motion.h1>

          <motion.p
            variants={headerVariants}
            className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            Select the reporting errors you want us to challenge this round. Only items that passed
            review and meet confidence rules are shown (same rules as the main app). Next you’ll pay
            for letter credits (or use existing credits), then we generate letter text — mail comes
            later.
          </motion.p>

          {loading ? (
            <motion.p variants={headerVariants} className="mt-10 text-center text-sm text-lab-muted">
              Loading your dispute plan…
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
                  "Dispute selection isn’t available for this workflow right now."}
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
                your current workflow step when it updates.
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
              <motion.div variants={headerVariants} className="mt-8">
                <StrategySummaryCard themesText={themesText} />
              </motion.div>

              {strategy.deterministic?.roundSummary ? (
                <motion.p
                  variants={headerVariants}
                  className="mx-auto mt-4 max-w-md text-center text-xs italic leading-relaxed text-lab-subtle sm:text-sm"
                >
                  {strategy.deterministic.roundSummary}
                </motion.p>
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
                      {g.items.map((it) => (
                        <li key={it.review_claim_id}>
                          <label className="flex cursor-pointer gap-3 rounded-lg px-1 py-2 transition-colors hover:bg-white/[0.04]">
                            <input
                              type="checkbox"
                              className="mt-1 h-4 w-4 shrink-0 rounded border-white/20 bg-lab-bg text-lab-accent focus:ring-lab-accent/40"
                              checked={selected.has(it.review_claim_id)}
                              onChange={() => toggleId(it.review_claim_id)}
                            />
                            <span className="text-sm leading-relaxed text-lab-text/90">
                              {claimLine(it)}
                            </span>
                          </label>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </motion.div>

              {authoritativeStepId && authoritativeStepId !== "select_disputes" ? (
                <p className="mt-8 text-center text-sm text-lab-muted">
                  Continue is available when your workflow is on the dispute-selection step.
                </p>
              ) : null}

              {submitError ? (
                <p className="mt-6 text-center text-sm text-red-300/90">{submitError}</p>
              ) : null}

              <motion.div variants={headerVariants} className="mt-10 sm:mt-12">
                <StrategyCTASection
                  onStart={() => void handleContinue()}
                  disabled={!canContinue}
                  label={submitting ? "Saving…" : "Continue to payment"}
                />
              </motion.div>
            </>
          ) : null}
        </motion.div>
      </main>
    </div>
  );
}
