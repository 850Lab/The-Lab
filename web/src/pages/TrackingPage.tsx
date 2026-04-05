import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BureauTrackingRow } from "@/components/BureauTrackingRow";
import { CreditCommandPlanSection } from "@/components/CreditCommandPlanSection";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { TrackingTruthStatusCard } from "@/components/TrackingTruthStatusCard";
import { TrackingStatesGuideCard } from "@/components/TrackingStatesGuideCard";
import { ExpectationsCard } from "@/components/ExpectationsCard";
import { ProgressTimelineCard } from "@/components/ProgressTimelineCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { TrackingDetailsModal } from "@/components/TrackingDetailsModal";
import type { CreditCommandPlanResponse } from "@/lib/letterTypes";
import {
  fetchCreditCommandPlan,
  fetchTrackingContext,
  postBeginNextDisputeRound,
} from "@/lib/workflowApi";
import type {
  TrackingBureauRow,
  TrackingContextPayload,
  TrackingContextResponse,
  TrackingModalBureau,
} from "@/lib/trackingTypes";
import type {
  CanonicalProgressionEscalationSummary,
  WorkflowEnvelope,
} from "@/lib/workflowTypes";
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
  r: TrackingContextResponse,
  applyWorkflowEnvelope: (e: WorkflowEnvelope) => void,
) {
  const merged: WorkflowEnvelope = {
    ...r.workflow,
    ...(r.progression !== undefined ? { progression: r.progression } : {}),
    ...(r.canonicalProgression !== undefined
      ? { canonicalProgression: r.canonicalProgression }
      : {}),
  };
  applyWorkflowEnvelope(merged);
}

function parseCanonicalEscalation(
  raw: unknown,
): CanonicalProgressionEscalationSummary | null {
  if (!raw || typeof raw !== "object") return null;
  const o = raw as Record<string, unknown>;
  const status = typeof o.status === "string" ? o.status : null;
  if (!status) return null;
  const actionCount = typeof o.actionCount === "number" ? o.actionCount : 0;
  const triggers = Array.isArray(o.triggers)
    ? o.triggers.filter((x): x is string => typeof x === "string")
    : [];
  const primaryActionType =
    typeof o.primaryActionType === "string" ? o.primaryActionType : null;
  const primaryActionId =
    typeof o.primaryActionId === "string" && o.primaryActionId.trim()
      ? o.primaryActionId.trim()
      : null;
  return {
    status,
    actionCount,
    primaryActionType,
    primaryActionId,
    triggers,
  };
}

function escalationTriggerExplanation(triggers: string[]): string {
  const parts: string[] = [];
  const set = new Set(triggers);
  const ordered = ["no_response", "repeated_verified", "insufficient_update"] as const;
  for (const k of ordered) {
    if (!set.has(k)) continue;
    if (k === "no_response") {
      parts.push(
        "There has been no substantive bureau response (or progress stalled) within the expected window for some disputed items.",
      );
    }
    if (k === "repeated_verified") {
      parts.push(
        "Some items were verified more than once without deletion — documenting method of verification and parallel paths is important.",
      );
    }
    if (k === "insufficient_update") {
      parts.push(
        "Partial bureau updates after multiple rounds suggest some negative or disputed data may still need targeted follow-up.",
      );
    }
  }
  if (parts.length === 0) {
    return "We’ve identified additional actions to move this forward.";
  }
  return parts.join(" ");
}

function trackingEscalationCta(esc: CanonicalProgressionEscalationSummary): {
  to: string;
  label: string;
} {
  if (esc.actionCount > 1) {
    return { to: "/escalation", label: "View escalation steps" };
  }
  const id = esc.primaryActionId?.trim();
  if (id) {
    return {
      to: `/escalation-action?action=${encodeURIComponent(id)}`,
      label: "Continue to the next escalation step",
    };
  }
  return { to: "/escalation", label: "View escalation steps" };
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

  const trackingEscalationUi = useMemo(() => {
    const raw = envelope?.canonicalProgression?.context?.escalation;
    const esc = parseCanonicalEscalation(raw);
    if (!esc) return { kind: "none" as const };
    const urgent = esc.status === "action_required";
    return {
      kind: urgent ? ("urgent" as const) : ("optional" as const),
      esc,
      explanation: escalationTriggerExplanation(esc.triggers),
      cta: trackingEscalationCta(esc),
    };
  }, [envelope]);

  const [beginNextBusy, setBeginNextBusy] = useState(false);
  const [beginNextError, setBeginNextError] = useState<string | null>(null);

  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [tracking, setTracking] = useState<TrackingContextPayload | null>(null);
  const [modalBureau, setModalBureau] = useState<TrackingModalBureau | null>(null);
  const [creditCommandPlanBundle, setCreditCommandPlanBundle] =
    useState<CreditCommandPlanResponse | null>(null);

  const loadContext = useCallback(async () => {
    if (!token || !workflowId) {
      setTracking(null);
      setCreditCommandPlanBundle(null);
      setLoadError(null);
      setPageLoading(false);
      return;
    }
    setPageLoading(true);
    setLoadError(null);
    try {
      const [data, planBundle] = await Promise.all([
        fetchTrackingContext(token, workflowId),
        fetchCreditCommandPlan(token, workflowId).catch(() => null),
      ]);
      applyTrackingResponse(data, applyWorkflowEnvelope);
      setTracking(data.tracking);
      setCreditCommandPlanBundle(planBundle);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setTracking(null);
      setCreditCommandPlanBundle(null);
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

  const overallComplete =
    (envelope?.workflowState?.overallStatus ?? "").toLowerCase() === "completed";

  const handleBeginNextRound = useCallback(async () => {
    if (!token || !workflowId) return;
    setBeginNextBusy(true);
    setBeginNextError(null);
    try {
      const r = await postBeginNextDisputeRound(token, workflowId);
      applyWorkflowEnvelope(r.workflow);
      navigate("/strategy", { replace: false });
    } catch (e) {
      setBeginNextError(e instanceof Error ? e.message : String(e));
    } finally {
      setBeginNextBusy(false);
    }
  }, [token, workflowId, applyWorkflowEnvelope, navigate]);

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
            Loading your program…
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
              className="text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-accent"
            >
              Your program · Tracking
            </motion.p>
            <motion.h1
              variants={headerVariants}
              className="mt-2 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
            >
              Your mail is in motion
            </motion.h1>
            <motion.p
              variants={headerVariants}
              className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
            >
              Real sends produce a timeline:{" "}
              <strong className="font-medium text-lab-text">sent</strong> →{" "}
              <strong className="font-medium text-lab-text">in process</strong> (carrier / bureau
              intake) → <strong className="font-medium text-lab-text">response</strong> (bureau reply
              window). Tracking shows USPS handoff and transit — not a guarantee the bureau finished
              reviewing; test sends never become physical mail.
            </motion.p>
            <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-sm">
              <ProgramFlowBridge>
                <span className="font-medium text-lab-text">After certified mail goes out,</span> this
                screen is your home for status. Refresh anytime; your next actions (including
                recording responses) stay in the same program.
              </ProgramFlowBridge>
            </motion.div>

            <motion.div variants={headerVariants}>
              <TrackingTruthStatusCard tracking={tracking} />
            </motion.div>

            {trackingEscalationUi.kind !== "none" ? (
              <motion.div
                variants={headerVariants}
                className={
                  trackingEscalationUi.kind === "urgent"
                    ? "mx-auto mt-5 max-w-sm rounded-xl border border-amber-500/35 bg-amber-500/10 px-4 py-4 shadow-lg shadow-black/10 sm:px-5 sm:py-5"
                    : "mx-auto mt-5 max-w-sm rounded-xl border border-white/[0.08] bg-lab-surface/90 px-4 py-4 sm:px-5 sm:py-5"
                }
              >
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-accent">
                  Your program
                </p>
                <h2 className="mt-1.5 text-base font-semibold text-lab-text sm:text-[17px]">
                  {trackingEscalationUi.kind === "urgent"
                    ? "Additional action needed"
                    : "Additional leverage available"}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                  Based on your results, the next step in your program may include structured
                  escalation — same program, not a separate tool.{" "}
                  {trackingEscalationUi.explanation}
                </p>
                <Link
                  to={trackingEscalationUi.cta.to}
                  className={
                    trackingEscalationUi.kind === "urgent"
                      ? "mt-4 inline-flex w-full items-center justify-center rounded-lg border border-lab-accent/45 bg-lab-accent/15 py-2.5 text-sm font-semibold text-lab-accent transition-colors hover:bg-lab-accent/25"
                      : "mt-4 inline-flex w-full items-center justify-center rounded-lg border border-white/[0.12] bg-white/[0.04] py-2.5 text-sm font-semibold text-lab-accent transition-colors hover:bg-white/[0.07]"
                  }
                >
                  {trackingEscalationUi.cta.label}
                </Link>
              </motion.div>
            ) : null}

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

              {creditCommandPlanBundle ? (
                <motion.div variants={subheadingVariants}>
                  <CreditCommandPlanSection
                    variant="tracking"
                    plan={creditCommandPlanBundle.creditCommandPlan}
                    unavailableReason={creditCommandPlanBundle.unavailableReason}
                  />
                </motion.div>
              ) : null}

              <motion.h2
                variants={subheadingVariants}
                className="text-sm font-semibold text-lab-text"
              >
                Status by bureau
              </motion.h2>

              <motion.div variants={subheadingVariants}>
                <TrackingStatesGuideCard />
              </motion.div>

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
                {trackingEscalationUi.kind === "none" ? (
                  <Link
                    to="/escalation"
                    className="mt-3 block w-full text-center text-sm font-medium text-lab-muted hover:text-lab-accent"
                  >
                    Need more leverage after a reply? Open the escalation toolkit →
                  </Link>
                ) : null}
              </motion.section>

              {overallComplete ? (
                <motion.section
                  variants={{
                    hidden: { opacity: 0, y: 16 },
                    show: {
                      opacity: 1,
                      y: 0,
                      transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
                    },
                  }}
                  className="rounded-xl border border-lab-accent/25 bg-lab-accent/[0.07] px-5 py-5 shadow-lg shadow-black/15 sm:px-6 sm:py-6"
                >
                  <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
                    Next phase: another dispute round
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                    When you are ready to challenge remaining items again, continue in the{" "}
                    <span className="font-medium text-lab-text">same program</span> — updated
                    strategy, new letters, and certified mail only where you still need bureau
                    action.
                  </p>
                  <button
                    type="button"
                    disabled={beginNextBusy}
                    onClick={() => void handleBeginNextRound()}
                    className="mt-4 w-full rounded-lg border border-lab-accent/45 bg-lab-accent/15 py-2.5 text-sm font-semibold text-lab-accent transition-colors hover:bg-lab-accent/25 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {beginNextBusy ? "Opening next round…" : "Continue program — next dispute round"}
                  </button>
                  {beginNextError ? (
                    <p className="mt-3 text-sm text-amber-200/95">{beginNextError}</p>
                  ) : null}
                </motion.section>
              ) : null}
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
