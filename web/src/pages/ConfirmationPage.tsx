import { LayoutGroup, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ContinueCTA } from "@/components/ContinueCTA";
import { DisputeGroupCard } from "@/components/DisputeGroupCard";
import { SummaryCard } from "@/components/SummaryCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { useIntakeSummary } from "@/hooks/useIntakeSummary";
import { postAcknowledgeReview } from "@/lib/workflowApi";
import { customerPathFromEnvelope } from "@/lib/workflowStepRoutes";
import {
  buildDisputeGroupsFromClaims,
  type DisputeGroupModel,
} from "@/lib/reviewClaimsDisplay";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

type RemovedSnapshot = {
  groupId: string;
  item: DisputeGroupModel["items"][number];
};

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.06 },
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

const groupListVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.14, delayChildren: 0.04 },
  },
};

const groupCardVariants = {
  hidden: { opacity: 0, y: 22 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.48, ease: [0.22, 1, 0.36, 1] },
  },
};

export function ConfirmationPage() {
  const navigate = useNavigate();
  const {
    token,
    workflowId,
    authoritativeStepId,
    canonicalCustomerPath,
    applyWorkflowEnvelope,
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

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[30%] z-0 h-[min(55vw,380px)] w-[min(55vw,380px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.05] blur-[100px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-xl px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <LayoutGroup>
          <motion.div variants={pageVariants} initial="hidden" animate="show">
            <motion.p
              variants={headerVariants}
              className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
            >
              Review
            </motion.p>

            <motion.h1
              variants={headerVariants}
              className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-3xl"
            >
              We’ve prepared this for you
            </motion.h1>

            <motion.p
              variants={headerVariants}
              className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
            >
              These items come from your parsed report — not letters yet. Next you’ll choose what to
              dispute, then pay for letter credits if needed.
            </motion.p>

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
                  Review opens when it’s the active step in your workflow.{" "}
                  {bundle?.workflow?.userMessage ? `(${bundle.workflow.userMessage})` : ""}
                </p>
                <Link
                  to={canonicalCustomerPath}
                  className="inline-block font-semibold text-lab-accent hover:text-sky-300"
                >
                  Go to your current step →
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

                <motion.div variants={headerVariants} className="mt-6">
                  <SummaryCard totalCount={visibleCount} />
                </motion.div>

                <motion.p
                  variants={headerVariants}
                  className="mx-auto mt-4 max-w-sm text-center text-xs leading-relaxed text-lab-subtle sm:text-sm"
                >
                  Most people continue with these as-is
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
                    label={submitting ? "Continuing…" : undefined}
                  />
                </motion.div>
              </>
            ) : null}
          </motion.div>
        </LayoutGroup>
      </main>
    </div>
  );
}
