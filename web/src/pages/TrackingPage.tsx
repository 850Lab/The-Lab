import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BureauTrackingRow } from "@/components/BureauTrackingRow";
import { TrackingTruthStatusCard } from "@/components/TrackingTruthStatusCard";
import { ExpectationsCard } from "@/components/ExpectationsCard";
import { ProgressTimelineCard } from "@/components/ProgressTimelineCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { TrackingDetailsModal } from "@/components/TrackingDetailsModal";
import { fetchTrackingContext } from "@/lib/workflowApi";
import type {
  TrackingBureauRow,
  TrackingContextPayload,
  TrackingModalBureau,
} from "@/lib/trackingTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";
import {
  customerPathFromEnvelope,
  isAuthoritativeStepBefore,
} from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.05 },
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

const stackVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.06 },
  },
};

const subheadingVariants = {
  hidden: { opacity: 0, y: 10 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.38, ease: [0.22, 1, 0.36, 1] },
  },
};

function applyTrackingResponse(
  r: { workflow: WorkflowEnvelope },
  applyWorkflowEnvelope: (e: WorkflowEnvelope) => void,
) {
  applyWorkflowEnvelope(r.workflow);
}

function homeGuidanceLines(
  tracking: import("@/lib/trackingTypes").TrackingContextPayload | null,
): string[] {
  const h = tracking?.homeSummary;
  if (!h) return [];
  const lines: string[] = [];
  const n = h.nextBestAction?.trim();
  if (n) lines.push(n);
  const w = h.waitingOn?.trim();
  if (w) lines.push(`Waiting on: ${w}`);
  const s = h.safeRouteHint?.trim();
  if (s) lines.push(s);
  return lines;
}

function rowKey(r: TrackingBureauRow): string {
  return `${r.bureau}-${String(r.reportId ?? "none")}`;
}

export function TrackingPage() {
  const navigate = useNavigate();
  const {
    token,
    workflowId,
    authoritativeStepId,
    envelope,
    applyWorkflowEnvelope,
    loading: ctxLoading,
  } = useCustomerWorkflow();

  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tracking, setTracking] = useState<TrackingContextPayload | null>(null);
  const [modalBureau, setModalBureau] = useState<TrackingModalBureau | null>(null);

  const loadContext = useCallback(async () => {
    if (!token || !workflowId) {
      setTracking(null);
      setLoadError(null);
      setPageLoading(false);
      return;
    }
    setPageLoading(true);
    setLoadError(null);
    try {
      const data = await fetchTrackingContext(token, workflowId);
      applyTrackingResponse(data, applyWorkflowEnvelope);
      setTracking(data.tracking);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setTracking(null);
    } finally {
      setPageLoading(false);
    }
  }, [token, workflowId, applyWorkflowEnvelope]);

  useEffect(() => {
    void loadContext();
  }, [loadContext]);

  useEffect(() => {
    if (pageLoading || loadError) return;
    if (!envelope) return;
    if (!authoritativeStepId) return;
    if (isAuthoritativeStepBefore(authoritativeStepId, "track")) {
      navigate(customerPathFromEnvelope(envelope), { replace: true });
    }
  }, [pageLoading, loadError, envelope, authoritativeStepId, navigate]);

  const guidanceLines = useMemo(() => homeGuidanceLines(tracking), [tracking]);

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[34%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[42%] z-0 h-[min(48vw,300px)] w-[min(48vw,300px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.04] blur-[90px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-28 pt-24 sm:px-6 sm:pb-32 sm:pt-28">
        {ctxLoading ? (
          <div className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-8 text-center text-sm text-lab-muted">
            Loading your workflow…
          </div>
        ) : !token ? (
          <div className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-8 text-center text-sm text-lab-muted">
            Sign in to view mailing and tracking status.
          </div>
        ) : !workflowId ? (
          <div className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-8 text-center text-sm text-lab-muted">
            No active workflow found. Start from the home flow.
          </div>
        ) : pageLoading ? (
          <div className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-8 text-center text-sm text-lab-muted">
            Loading tracking status…
          </div>
        ) : loadError ? (
          <div className="space-y-4 rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-6">
            <p className="text-sm text-amber-200/95">{loadError}</p>
            <button
              type="button"
              onClick={() => void loadContext()}
              className="w-full rounded-lg border border-white/[0.12] py-2.5 text-sm font-medium text-lab-text hover:bg-white/[0.04]"
            >
              Try again
            </button>
          </div>
        ) : tracking ? (
          <motion.div
            variants={pageVariants}
            initial="hidden"
            animate="show"
            className="pb-4"
          >
            <div className="mb-6 flex items-center justify-end">
              <button
                type="button"
                onClick={() => void loadContext()}
                className="text-sm font-medium text-lab-accent hover:text-sky-300"
              >
                Refresh status
              </button>
            </div>

            <motion.p
              variants={headerVariants}
              className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
            >
              Tracking
            </motion.p>
            <motion.h1
              variants={headerVariants}
              className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
            >
              Your disputes are in progress
            </motion.h1>
            <motion.p
              variants={headerVariants}
              className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
            >
              Same definitions as the send step: test submissions never produce USPS mail; tracking
              shows carrier handoff and transit, not guaranteed delivery to the bureau.
            </motion.p>

            <motion.div variants={headerVariants}>
              <TrackingTruthStatusCard tracking={tracking} />
            </motion.div>

            {tracking.mailGateFailedSendCount > 0 ? (
              <motion.div
                variants={headerVariants}
                className="mx-auto mt-5 max-w-sm rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-lab-text"
              >
                <p className="font-medium text-amber-100/95">
                  {tracking.mailGateFailedSendCount} send
                  {tracking.mailGateFailedSendCount === 1 ? "" : "s"} need attention
                </p>
                {tracking.mailGateLastFailureMessageSafe ? (
                  <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                    {tracking.mailGateLastFailureMessageSafe}
                  </p>
                ) : null}
              </motion.div>
            ) : null}

            <motion.div
              variants={stackVariants}
              initial="hidden"
              animate="show"
              className="mt-10 flex flex-col gap-5 sm:mt-11 sm:gap-6"
            >
              <ProgressTimelineCard
                dayCurrent={tracking.timeline.daysSinceFirstMail}
                totalDays={tracking.timeline.timelineTotalDays}
              />

              <motion.h2
                variants={subheadingVariants}
                className="text-sm font-semibold text-lab-text"
              >
                Your letters
              </motion.h2>

              {!tracking.hasTargets ? (
                <motion.p
                  variants={subheadingVariants}
                  className="text-sm leading-relaxed text-lab-muted"
                >
                  Nothing to list yet — mail targets come from your dispute selection and
                  reports.
                </motion.p>
              ) : (
                tracking.bureauRows.map((row) => (
                  <BureauTrackingRow
                    key={rowKey(row)}
                    bureau={row.bureauDisplay}
                    status={row.displayStatus}
                    onViewDetails={() => setModalBureau(row)}
                  />
                ))
              )}

              <ExpectationsCard extraLines={guidanceLines} />

              <motion.section
                variants={{
                  hidden: { opacity: 0, y: 16 },
                  show: {
                    opacity: 1,
                    y: 0,
                    transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
                  },
                }}
                className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 shadow-lg shadow-black/15 sm:px-6 sm:py-6"
              >
                <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
                  Bureau responses
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                  When a bureau or furnisher replies, add a short summary under Responses — we classify
                  it and show your next step (same backend as the main app).
                </p>
                <Link
                  to="/responses"
                  className="mt-4 inline-flex w-full items-center justify-center rounded-lg border border-lab-accent/35 bg-lab-accent/10 py-2.5 text-sm font-semibold text-lab-accent transition-colors hover:bg-lab-accent/18"
                >
                  Record a bureau or furnisher response
                </Link>
              </motion.section>
            </motion.div>
          </motion.div>
        ) : null}
      </main>

      <TrackingDetailsModal
        open={modalBureau !== null}
        onClose={() => setModalBureau(null)}
        bureau={modalBureau}
      />
    </div>
  );
}
