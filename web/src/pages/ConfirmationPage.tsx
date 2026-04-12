import { LayoutGroup, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ContinueCTA } from "@/components/ContinueCTA";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import {
  ReviewPhaseProgressStrip,
  ReviewReassuranceBlock,
} from "@/components/ReviewStepContinuity";
import { DisputeGroupCard } from "@/components/DisputeGroupCard";
import { SummaryCard } from "@/components/SummaryCard";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { useIntakeSummary } from "@/hooks/useIntakeSummary";
import { postAcknowledgeReview } from "@/lib/workflowApi";
import { customerPathFromEnvelope } from "@/lib/workflowStepRoutes";
import {
  buildDisputeGroupsFromClaims,
  type DisputeGroupModel,
} from "@/lib/reviewClaimsDisplay";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  orionStepHeroCopy,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import {
  stepCardChildVariants as groupCardVariants,
  stepNestedStaggerVariants as groupListVariants,
  stepChildVariants as headerVariants,
  stepPageVariants as pageVariants,
} from "@/lib/motionStep";

type RemovedSnapshot = {
  groupId: string;
  item: DisputeGroupModel["items"][number];
};

const CONFIRMATION_HERO_FALLBACK = {
  title: "Finalize what belongs in this round",
  subtitle:
    "This step confirms the items from your findings before building your strategy. The list below is organized for you — remove anything that doesn't belong in this round.",
} as const;

export function ConfirmationPage() {
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
  const { bundle, loading, error } = useIntakeSummary();
  const [groups, setGroups] = useState<DisputeGroupModel[]>([]);
  const [lastRemoved, setLastRemoved] = useState<RemovedSnapshot | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const seededRef = useRef(false);

  useEffect(() => {
    if (!bundle) {
      seededRef.current = false;
      return;
    }
    if (seededRef.current) return;
    setGroups(buildDisputeGroupsFromClaims(bundle.intake.reviewClaims));
    seededRef.current = true;
  }, [bundle]);

  const removeItem = useCallback((groupId: string, itemId: string) => {
    setGroups((prev) => {
      const g = prev.find((x) => x.id === groupId);
      const item = g?.items.find((i) => i.id === itemId);
      if (item) {
        setLastRemoved({ groupId, item: { ...item } });
      }
      return prev.map((gr) =>
        gr.id === groupId ? { ...gr, items: gr.items.filter((i) => i.id !== itemId) } : gr,
      );
    });
  }, []);

  const undoRemove = useCallback(() => {
    if (!lastRemoved) return;
    const { groupId, item } = lastRemoved;
    setGroups((prev) =>
      prev.map((gr) =>
        gr.id === groupId ? { ...gr, items: [...gr.items, item].sort((a, b) => a.order - b.order) } : gr,
      ),
    );
    setLastRemoved(null);
  }, [lastRemoved]);

  const visibleCount = groups.reduce((n, g) => n + g.items.length, 0);
  const canContinue =
    !!token &&
    !!workflowId &&
    authoritativeStepId === "review_claims" &&
    !submitting &&
    !loading;

  const handleContinue = async () => {
    if (!token || !workflowId || !canContinue) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const r = await postAcknowledgeReview(token, workflowId, {
        item_count: visibleCount,
      });
      applyWorkflowEnvelope(r.workflow);
      navigate(customerPathFromEnvelope(r.workflow), { replace: true });
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const intake = bundle?.intake;
  const reportRows = intake?.reports ?? [];

  const orionAuthority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const confirmationHero = useMemo(
    () => orionStepHeroCopy(orionAuthority, orionViewModel, CONFIRMATION_HERO_FALLBACK),
    [orionAuthority, orionViewModel],
  );

  return (
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn className="relative z-10 mx-auto max-w-xl px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <LayoutGroup>
          <motion.div variants={pageVariants} initial="hidden" animate="show">
            <motion.p
              variants={headerVariants}
              className="step-eyebrow"
            >
              STEP 2 • CONFIRM YOUR REVIEW
            </motion.p>

            <motion.h1
              variants={headerVariants}
              className="step-title"
            >
              {confirmationHero.title}
            </motion.h1>

            {authoritativeStepId === "review_claims" ? (
              <motion.div
                variants={headerVariants}
                className="mx-auto mt-5 flex max-w-md flex-col items-stretch gap-2 sm:flex-row sm:justify-center sm:gap-3"
              >
                <Link
                  to="/upload"
                  className="inline-flex items-center justify-center rounded-xl border border-white/[0.14] bg-white/[0.04] px-4 py-2.5 text-center text-sm font-semibold text-lab-text hover:bg-white/[0.07]"
                >
                  Add another report
                </Link>
                <Link
                  to="/analyze"
                  className="link-step inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-center text-sm"
                >
                  Back to your review list
                </Link>
              </motion.div>
            ) : null}

            <motion.p
              variants={headerVariants}
              className={`step-support max-w-md ${
                authoritativeStepId === "review_claims" ? "!mt-4" : ""
              }`}
            >
              {confirmationHero.subtitle}
            </motion.p>

            <motion.div variants={headerVariants} className="mx-auto max-w-2xl">
              <ReviewPhaseProgressStrip phase="prepare" />
            </motion.div>
            <motion.div variants={headerVariants}>
              <ReviewReassuranceBlock />
            </motion.div>

            <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-md">
              <ProgramFlowBridge>
                <span className="font-medium text-lab-text">Review before strategy:</span> what stays on
                this list is what we&apos;ll use to build your dispute round. When you&apos;re ready, continue
                to strategy — no pressure to rush.
              </ProgramFlowBridge>
            </motion.div>

            {loading && !bundle ? (
              <motion.p variants={headerVariants} className="mt-10 text-center text-sm text-lab-muted">
                Loading review items…
              </motion.p>
            ) : null}

            {error ? (
              <motion.p variants={headerVariants} className="mt-10 text-center text-sm text-red-300/90">
                {error}
              </motion.p>
            ) : null}

            {authoritativeStepId && authoritativeStepId !== "review_claims" ? (
              <motion.div
                variants={headerVariants}
                className="mt-8 space-y-3 text-center text-sm text-lab-muted"
              >
                <p>
                  Review opens when it’s the active step in your program.{" "}
                  {bundle?.workflow?.userMessage ? `(${bundle.workflow.userMessage})` : ""}
                </p>
                <Link
                  to={canonicalCustomerPath}
                  className="inline-block font-semibold text-lab-accent hover:text-zinc-100"
                >
                  Continue in your program →
                </Link>
              </motion.div>
            ) : null}

            {bundle && authoritativeStepId === "review_claims" ? (
              <>
                {reportRows.length > 0 ? (
                  <motion.div variants={headerVariants} className="mt-8 text-center text-xs text-lab-subtle">
                    Based on {reportRows.length}{" "}
                    {reportRows.length === 1 ? "report" : "reports"} on file
                    {intake?.aggregates?.totalAccountsExtracted != null
                      ? ` · ${intake.aggregates.totalAccountsExtracted} accounts parsed`
                      : ""}
                  </motion.div>
                ) : null}

                {visibleCount > 0 ? (
                  <motion.div variants={headerVariants} className="mt-6">
                    <SummaryCard
                      totalCount={visibleCount}
                      subline="You can trim the list if something doesn’t apply — we’ll use what’s left for strategy."
                    />
                  </motion.div>
                ) : null}

                <motion.p
                  variants={headerVariants}
                  className="mx-auto mt-4 max-w-sm text-center text-xs leading-relaxed text-lab-subtle sm:text-sm"
                >
                  Most people keep the suggested items — the system already filtered to what’s worth a
                  look.
                </motion.p>

                {groups.some((g) => g.items.length > 0) ? (
                  <motion.div
                    variants={groupListVariants}
                    className="mt-10 space-y-8 sm:mt-12 sm:space-y-10"
                  >
                    {groups.map((g) =>
                      g.items.length > 0 ? (
                        <DisputeGroupCard
                          key={g.id}
                          title={g.title}
                          items={g.items}
                          onRemoveItem={(itemId) => removeItem(g.id, itemId)}
                          groupVariants={groupCardVariants}
                        />
                      ) : null,
                    )}
                  </motion.div>
                ) : (
                  <motion.p
                    variants={headerVariants}
                    className="mt-10 text-center text-sm text-lab-muted"
                  >
                    {reportRows.length > 0
                      ? "No review items were generated from your report. You can still continue to the next step."
                      : "No parsed report data found yet. Upload a report first, then return here."}
                  </motion.p>
                )}

                {lastRemoved ? (
                  <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-6 flex justify-center"
                  >
                    <button
                      type="button"
                      onClick={undoRemove}
                      className="text-sm font-medium text-lab-accent/90 transition-colors hover:text-lab-accent"
                    >
                      Undo
                    </button>
                  </motion.div>
                ) : null}

                {submitError ? (
                  <p className="mt-6 text-center text-sm text-red-300/90">{submitError}</p>
                ) : null}

                <motion.div variants={headerVariants} className="mt-12 sm:mt-14">
                  <ContinueCTA
                    onClick={() => void handleContinue()}
                    disabled={!canContinue}
                    label={submitting ? "Continuing…" : "Continue to strategy"}
                  />
                </motion.div>
              </>
            ) : null}
          </motion.div>
        </LayoutGroup>
      </StepMainColumn>
    </div>
  );
}
