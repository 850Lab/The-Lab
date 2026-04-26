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
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
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
import { easeStep } from "@/lib/motionStep";
import {
  customerPathFromEnvelope,
  isAuthoritativeStepBefore,
} from "@/lib/workflowStepRoutes";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  orionNarrativeCoherent,
  orionStepHeroCopy,
  orionWaitingOrPassivePrimary,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import {
  stepChildVariants as headerVariants,
  stepChildVariants as subheadingVariants,
  stepPageVariants as pageVariants,
  stepStackVariants as stackVariants,
} from "@/lib/motionStep";

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
    return { to: "/escalation", label: "Review escalation options" };
  }
  const id = esc.primaryActionId?.trim();
  if (id) {
    return {
      to: `/escalation-action?action=${encodeURIComponent(id)}`,
      label: "Continue this escalation path",
    };
  }
  return { to: "/escalation", label: "Review escalation options" };
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

function TrackingProgressStrip({
  trackingStepComplete,
}: {
  trackingStepComplete: boolean;
}) {
  const step2Done = trackingStepComplete;
  const step3Active = trackingStepComplete;

  return (
    <motion.div
      variants={headerVariants}
      className="surface-where-fits mx-auto mt-6 max-w-2xl"
    >
      <p className="text-center text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
        What happens next
      </p>
      <ol className="mt-3 flex flex-col gap-2 text-sm sm:mt-4 sm:flex-row sm:justify-center sm:gap-3 sm:text-[13px]">
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted">
          <span className="font-semibold text-emerald-200/95">1.</span>
          <span className="ml-1.5">Mailing confirmed</span>
        </li>
        <li
          className={
            step2Done
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text"
          }
        >
          <span className={step2Done ? "font-semibold text-emerald-200/95" : "text-lab-accent"}>
            2.
          </span>
          <span className="ml-1.5">Tracking in progress</span>
        </li>
        <li
          className={
            step3Active
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted"
          }
        >
          <span className={step3Active ? "text-lab-accent" : "text-lab-subtle"}>3.</span>
          <span className="ml-1.5">Responses or next round later</span>
        </li>
      </ol>
    </motion.div>
  );
}

function TrackingRoundContinuityModule({ tracking }: { tracking: TrackingContextPayload }) {
  const targets = tracking.bureauRows.length;
  const mailed = tracking.mailedBureauCount;
  const phase = tracking.linearPhase?.trim();

  return (
    <div className="surface-round-continuity">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-lab-subtle">
        Your current round
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        Mailing was confirmed in the last step. This page shows delivery and status for that package
        — USPS progress and bureau timelines are different. When updates arrive, your next actions may
        include logging responses, another round, or escalation — not all at once.
      </p>
      {targets > 0 ? (
        <p className="mt-2 text-xs text-lab-subtle">
          {mailed} of {targets} bureau target{targets === 1 ? "" : "s"} with mailed activity recorded
          {phase ? ` · ${phase}` : ""}.
        </p>
      ) : (
        <p className="mt-2 text-xs text-lab-subtle">
          Tracking will appear after a successful send from the mailing step.
        </p>
      )}
    </div>
  );
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
    orionViewModel,
    integrityHints,
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
    /** Allow tracking UI when mail is server-blocked; step may still be `mail` authoritatively. */
    if (integrityHints?.mailBlocked) return;
    if (isAuthoritativeStepBefore(authoritativeStepId, "track")) {
      navigate(customerPathFromEnvelope(envelope), { replace: true });
    }
  }, [
    pageLoading,
    loadError,
    envelope,
    authoritativeStepId,
    navigate,
    integrityHints?.mailBlocked,
  ]);

  const guidanceLines = useMemo(() => homeGuidanceLines(tracking), [tracking]);

  const TRACKING_HERO_FALLBACK = {
    title: "Follow the progress of the package you mailed",
    subtitle:
      "This page helps you track what has happened since mailing was confirmed. Delivery progress and bureau response timelines are shown separately so you can see what to watch next.",
  } as const;

  const orionAuthority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const trackingHero = useMemo(
    () => orionStepHeroCopy(orionAuthority, orionViewModel, TRACKING_HERO_FALLBACK),
    [orionAuthority, orionViewModel],
  );

  const trackingCoherent = useMemo(
    () => orionNarrativeCoherent(orionAuthority, orionViewModel),
    [orionAuthority, orionViewModel],
  );
  const trackingPassiveOrion = useMemo(
    () => trackingCoherent && orionWaitingOrPassivePrimary(orionAuthority),
    [trackingCoherent, orionAuthority],
  );

  const expectationsExtraLines = useMemo(() => {
    if (trackingPassiveOrion) return [];
    return guidanceLines;
  }, [trackingPassiveOrion, guidanceLines]);

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
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn
        className={`relative z-10 mx-auto max-w-xl px-4 pb-28 sm:px-6 sm:pb-32 ${stepMainColumnTopClass(!!workflowId)}`}
      >
        {ctxLoading ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-8 text-center text-sm text-lab-muted"
          >
            Loading your program…
          </motion.div>
        ) : !token ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-8 text-center text-sm text-lab-muted"
          >
            Sign in to view mailing and tracking status.
          </motion.div>
        ) : !workflowId ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-8 text-center text-sm text-lab-muted"
          >
            No active workflow found. Start from the home flow.
          </motion.div>
        ) : pageLoading ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-8 text-center text-sm text-lab-muted"
          >
            Loading tracking status…
          </motion.div>
        ) : loadError ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="space-y-4 rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-6"
          >
            <p className="text-sm text-amber-200/95">{loadError}</p>
            <button
              type="button"
              onClick={() => void loadContext()}
              className="w-full rounded-lg border border-white/[0.12] py-2.5 text-sm font-medium text-lab-text hover:bg-white/[0.04]"
            >
              Try again
            </button>
          </motion.div>
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
                className="link-step text-sm"
              >
                Refresh status
              </button>
            </div>

            <motion.h2
              variants={headerVariants}
              className="step-title"
            >
              {trackingHero.title}
            </motion.h2>
            <motion.p
              variants={headerVariants}
              className="step-support"
            >
              {trackingHero.subtitle}
            </motion.p>
            <motion.div
              variants={headerVariants}
              className="surface-emerald-reassure mx-auto mt-6 max-w-lg"
            >
              <ul className="space-y-2 text-left text-sm leading-relaxed text-emerald-50/95 sm:text-[15px]">
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>Your mailing was confirmed in the last step</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>Mail delivery and bureau review happen on different timelines</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>It is normal for this stage to include waiting between updates</span>
                </li>
              </ul>
            </motion.div>

            <TrackingProgressStrip trackingStepComplete={tracking.trackStepCompleted} />

            <motion.div variants={headerVariants} className="mx-auto mt-6 max-w-lg">
              <TrackingRoundContinuityModule tracking={tracking} />
            </motion.div>

            <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-lg">
              <ProgramFlowBridge>
                {trackingPassiveOrion ? (
                  <>
                    <span className="font-medium text-lab-text">Tracking for this round</span> — use
                    refresh for updates; quiet periods are often normal while mail and bureaus move on
                    their own timelines.
                  </>
                ) : (
                  <>
                    <span className="font-medium text-lab-text">Tracking starts here</span> — after you
                    confirmed mailing. Use refresh for the latest; responses and escalation come later in
                    the program when they make sense.
                  </>
                )}
              </ProgramFlowBridge>
            </motion.div>

            {!trackingPassiveOrion ? (
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-5 max-w-lg text-center text-xs leading-relaxed text-lab-subtle sm:text-sm"
              >
                This is the control point before you chase outcomes: watch mail movement first, then
                bureau replies on their own clock — no update yet often just means “still in progress.”
              </motion.p>
            ) : null}

            <motion.div variants={headerVariants}>
              <TrackingTruthStatusCard tracking={tracking} />
            </motion.div>

            {trackingEscalationUi.kind !== "none" ? (
              <motion.div
                variants={headerVariants}
                className={
                  trackingEscalationUi.kind === "urgent"
                    ? "mx-auto mt-5 max-w-lg rounded-xl border border-amber-500/35 bg-amber-500/10 px-4 py-4 shadow-lg shadow-black/10 sm:px-5 sm:py-5"
                    : "mx-auto mt-5 max-w-lg rounded-xl border border-white/[0.08] bg-lab-surface/90 px-4 py-4 sm:px-5 sm:py-5"
                }
              >
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
                  Your program
                </p>
                <h2 className="mt-1.5 text-base font-semibold text-lab-text sm:text-[17px]">
                  {trackingEscalationUi.kind === "urgent"
                    ? "Optional next steps when you’re ready"
                    : "More options when it fits your timeline"}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                  When your situation calls for it, the same program may offer structured follow-up —
                  not a separate tool. {trackingEscalationUi.explanation}
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
                className="mx-auto mt-5 max-w-lg rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 text-sm text-lab-text"
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
              <motion.div variants={subheadingVariants}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
                  Mail delivery progress
                </p>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                  The timeline below is <span className="font-medium text-lab-text">typical mail</span>{" "}
                  first, then <span className="font-medium text-lab-text">bureau review</span> — they
                  are not the same clock.
                </p>
              </motion.div>

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

              <motion.div variants={subheadingVariants}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
                  Mail and tracking by bureau
                </p>
                <h2 className="mt-2 text-base font-semibold text-lab-text sm:text-[17px]">
                  USPS / send status for each target
                </h2>
                <p className="mt-1 text-sm leading-relaxed text-lab-muted">
                  These rows show mail and carrier status — not whether a bureau has finished its
                  investigation.
                </p>
              </motion.div>

              <details className="details-calm rounded-xl border border-white/[0.08] bg-lab-surface/80 px-4 py-3 sm:px-5 sm:py-4">
                <summary className="cursor-pointer list-none text-sm font-medium text-lab-muted [&::-webkit-details-marker]:hidden">
                  Status labels (optional detail) ▾
                </summary>
                <div className="mt-3">
                  <TrackingStatesGuideCard embedded />
                </div>
              </details>

              {!tracking.hasTargets ? (
                <motion.p
                  variants={subheadingVariants}
                  className="text-sm leading-relaxed text-lab-muted"
                >
                  Tracking will appear after a successful send from the mailing step. Delivery updates
                  may take a little time to show once mail is in motion.
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

              <ExpectationsCard
                extraLines={expectationsExtraLines}
                heading="What usually happens next · when to keep waiting"
              />

              <motion.section
                variants={{
                  hidden: { opacity: 0, y: 16 },
                  show: {
                    opacity: 1,
                    y: 0,
                    transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
                  },
                }}
                className="rounded-xl border border-white/[0.08] bg-lab-bg/50 px-5 py-5 sm:px-6 sm:py-6"
              >
                <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
                  Stay with this round as updates come in
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                  You don&apos;t need to act on every quiet day. Use this page to monitor delivery and
                  wait for meaningful changes before moving to the next action in your program.
                </p>
              </motion.section>

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
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
                  After delivery: bureau outcomes
                </p>
                <h3 className="mt-2 text-[15px] font-semibold text-lab-text sm:text-base">
                  Log a response when mail arrives
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                  When a bureau or furnisher replies by mail or online, you can add a short summary on
                  the Responses step — we help classify it and suggest what&apos;s next. No rush until
                  you have something real to record.
                </p>
                <Link
                  to="/responses"
                  className="mt-4 inline-flex w-full items-center justify-center rounded-lg border border-lab-accent/35 bg-lab-accent/10 py-2.5 text-sm font-semibold text-lab-accent transition-colors hover:bg-lab-accent/18"
                >
                  View Responses
                </Link>
                {trackingEscalationUi.kind === "none" ? (
                  <Link
                    to="/escalation"
                    className="mt-3 block w-full text-center text-xs font-medium text-lab-subtle hover:text-lab-accent"
                  >
                    Later: review escalation options if you need more leverage →
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
                  className="rounded-xl border border-zinc-700/50 bg-lab-elevated/90 px-5 py-5 shadow-lg shadow-black/25 sm:px-6 sm:py-6"
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
      </StepMainColumn>

      <TrackingDetailsModal
        open={modalBureau !== null}
        onClose={() => setModalBureau(null)}
        bureau={modalBureau}
      />
    </div>
  );
}
