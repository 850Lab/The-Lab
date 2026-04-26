import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { NarrativeSummaryCard } from "@/components/NarrativeSummaryCard";
import { ReportSectionCard } from "@/components/structuredReport/ReportSectionCard";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type { IntakeSummaryBundle } from "@/lib/intakeTypes";
import { buildFindingGroupsFromClaims } from "@/lib/reviewClaimsDisplay";
import { labelForReviewType } from "@/lib/reviewClaimsDisplay";
import { FREE_VALUE_LINE } from "@/lib/flowMicrocopy";
import { buildNarrativeInputForStructuredReport } from "@/lib/narrativeBuilder";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";
import { strategyConfidenceUserLabel, strategyConfidencePillClass } from "@/lib/strategyRecommendationUi";
import type { DisputeStrategyBundle, DisputeStrategyPayload, ReviewClaimWithRecommendation } from "@/lib/strategyTypes";
import type { LettersContextResponse } from "@/lib/letterTypes";
import type { MailContextResponse } from "@/lib/mailTypes";
import type { PaymentContextResponse } from "@/lib/paymentTypes";
import type { ProofContextResponse } from "@/lib/proofTypes";
import type { TrackingContextResponse } from "@/lib/trackingTypes";
import type { EscalationLayerResponse } from "@/lib/escalationLayerTypes";
import type { WorkflowResponseMetricsResponse } from "@/lib/responseTypes";
import {
  fetchIntakeSummary,
  fetchDisputeStrategy,
  fetchLettersContext,
  fetchLettersBundleTxt,
  fetchPaymentContext,
  fetchMailContext,
  fetchProofContext,
  fetchTrackingContext,
  fetchWorkflowResponseMetrics,
  fetchEscalationLayer,
} from "@/lib/workflowApi";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import { stepPageVariants } from "@/lib/motionStep";
import { motion } from "framer-motion";

function impactLabel(l: "high" | "medium" | "low" | undefined): string {
  if (l === "high") return "High impact";
  if (l === "medium") return "Medium impact";
  if (l === "low") return "Lower impact";
  return "";
}

type FlatItem = ReviewClaimWithRecommendation & { groupType: string };

function flattenStrategyItems(payload: DisputeStrategyPayload | null): FlatItem[] {
  if (!payload) return [];
  return payload.groups.flatMap((g) =>
    g.items.map((it) => ({ ...it, groupType: g.reviewType })),
  );
}

const pageMotion = stepPageVariants;

/**
 * Read-only customer report composed from existing workflow APIs. Does not post or advance steps.
 */
export function StructuredReportPage() {
  const { token } = useAuth();
  const { workflowId, programState, integrityHints, orionViewModel } = useCustomerWorkflow();
  const inShell = Boolean(workflowId);

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [intake, setIntake] = useState<IntakeSummaryBundle | null>(null);
  const [strategy, setStrategy] = useState<DisputeStrategyBundle | null>(null);
  const [letters, setLetters] = useState<LettersContextResponse | null>(null);
  const [payment, setPayment] = useState<PaymentContextResponse | null>(null);
  const [mail, setMail] = useState<MailContextResponse | null>(null);
  const [proof, setProof] = useState<ProofContextResponse | null>(null);
  const [tracking, setTracking] = useState<TrackingContextResponse | null>(null);
  const [responseMetrics, setResponseMetrics] = useState<WorkflowResponseMetricsResponse | null>(
    null,
  );
  const [escalation, setEscalation] = useState<EscalationLayerResponse | null>(null);

  const [downloading, setDownloading] = useState(false);
  const [dlError, setDlError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token || !workflowId) {
      setLoading(false);
      return;
    }
    setLoadError(null);
    setLoading(true);
    const t = token;
    const w = workflowId;
    const settled = await Promise.allSettled([
      fetchIntakeSummary(t, w),
      fetchDisputeStrategy(t, w),
      fetchLettersContext(t, w),
      fetchPaymentContext(t, w),
      fetchMailContext(t, w),
      fetchProofContext(t, w),
      fetchTrackingContext(t, w),
      fetchWorkflowResponseMetrics(t, w),
      fetchEscalationLayer(t, w).catch(() => null),
    ]);
    const s = settled;
    if (s[0].status === "fulfilled") setIntake(s[0].value);
    if (s[1].status === "fulfilled") setStrategy(s[1].value);
    if (s[2].status === "fulfilled") setLetters(s[2].value);
    if (s[3].status === "fulfilled") setPayment(s[3].value);
    if (s[4].status === "fulfilled") setMail(s[4].value);
    if (s[5].status === "fulfilled") setProof(s[5].value);
    if (s[6].status === "fulfilled") setTracking(s[6].value);
    if (s[7].status === "fulfilled") setResponseMetrics(s[7].value);
    if (s[8].status === "fulfilled" && s[8].value)
      setEscalation(s[8].value as EscalationLayerResponse);
    setLoading(false);
  }, [token, workflowId]);

  useEffect(() => {
    void load();
  }, [load]);

  const findingGroups = useMemo(() => {
    const claims = intake?.intake.reviewClaims ?? [];
    if (claims.length === 0) return [];
    return buildFindingGroupsFromClaims(claims);
  }, [intake]);

  const strategyPayload = strategy?.disputeStrategy ?? null;
  const flatItems = useMemo(() => flattenStrategyItems(strategyPayload), [strategyPayload]);
  const suggestedIds = new Set(strategyPayload?.suggestedReviewClaimIds ?? []);

  const onDownloadBundle = useCallback(async () => {
    if (!token || !workflowId) return;
    setDlError(null);
    setDownloading(true);
    try {
      const text = await fetchLettersBundleTxt(token, workflowId);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
      a.download = "850-lab-dispute-letters.txt";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) {
      setDlError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setDownloading(false);
    }
  }, [token, workflowId]);

  const p = programState;
  const parseDone = p?.progress.completedSteps?.includes("parse_analyze");
  const hasClaimRows = (intake?.intake.reviewClaims.length ?? 0) > 0;
  const canShowFindings = Boolean(parseDone || hasClaimRows);
  const nba = p?.nextBestAction;
  const backHref = p?.canonicalRoute ?? "/";

  const analysisPending = useMemo(
    () =>
      Boolean(
        programState &&
          programState.currentStep === "parse_analyze" &&
          !programState.progress.completedSteps.includes("parse_analyze"),
      ),
    [programState],
  );

  const narrativeInput = useMemo(
    () =>
      buildNarrativeInputForStructuredReport(
        programState,
        intake,
        strategy,
        responseMetrics,
        mail,
        letters,
        analysisPending,
      ),
    [programState, intake, strategy, responseMetrics, mail, letters, analysisPending],
  );

  if (!token) {
    return null;
  }
  if (!workflowId) {
    return <Navigate to="/" replace />;
  }

  return (
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />
      <TopBarMinimal />

      <StepMainColumn
        className={`relative z-10 mx-auto max-w-xl px-4 pb-28 sm:px-6 sm:pb-32 ${stepMainColumnTopClass(inShell)}`}
      >
        <motion.div
          className="space-y-5 pb-4"
          variants={pageMotion}
          initial="hidden"
          animate="show"
        >
          <div className="text-center sm:text-left">
            <h2 className="text-xl font-semibold text-lab-text sm:text-2xl">Your structured report</h2>
            <p className="mt-1 text-sm text-lab-subtle">
              Read-only snapshot from your file and program. Use the main steps to continue—nothing
              here changes your place in the program.
            </p>
            <p className="mt-2">
              <Link
                to={backHref}
                className="text-sm font-medium text-lab-accent/95 underline decoration-lab-accent/30 underline-offset-2 hover:decoration-lab-accent/60"
              >
                Back to your current step
              </Link>
            </p>
          </div>

          {!loadError && !loading ? (
            <NarrativeSummaryCard input={narrativeInput} className="mt-4" />
          ) : null}

          {!loadError && !loading ? (
            <div className="mt-3 rounded-lg border border-white/[0.06] bg-lab-surface/50 px-4 py-3 sm:px-4 sm:py-3.5">
              <p className="text-xs leading-relaxed text-lab-muted sm:text-sm">
                {FREE_VALUE_LINE} Mailing and tracking in the app are optional as you go — use them when
                you want a guided send instead of doing everything yourself.
              </p>
            </div>
          ) : null}

          {loadError ? (
            <p className="text-center text-sm text-red-300/95">{loadError}</p>
          ) : null}

          {loading ? (
            <p className="text-center text-sm text-lab-muted">Loading report…</p>
          ) : null}

          {!loading && !parseDone && p?.currentStep === "parse_analyze" && (
            <ReportSectionCard
              title="Credit findings summary"
              description="We’re still analyzing your upload. A structured summary of findings will show here when analysis finishes."
            >
              <p className="text-lab-muted/90">Analysis in progress. Check the Analysis step for live status.</p>
            </ReportSectionCard>
          )}

          <ReportSectionCard
            title="Program snapshot"
            description="From your current program state—same as the top of this screen."
          >
            {p ? (
              <ul className="list-none space-y-2.5 text-left text-sm text-lab-muted">
                <li>
                  <span className="font-medium text-lab-text">Current step: </span>
                  {p.currentStep ?? "—"}
                </li>
                <li>
                  <span className="font-medium text-lab-text">Next action: </span>
                  {nba
                    ? `${nba.label} → ${nba.targetRoute}`
                    : "Follow the program step to continue"}
                </li>
                <li>
                  <span className="font-medium text-lab-text">Progress: </span>
                  {p.progress.completedSteps.length} of {p.progress.total} milestones recorded
                </li>
                <li>
                  <span className="font-medium text-lab-text">Round: </span>
                  {p.isComplete ? "This guided round is complete" : "In progress"}
                </li>
                {integrityHints?.mailBlocked ? (
                  <li className="rounded-md border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-amber-100/90">
                    Mail partner send is blocked—your program can still use tracking. Use the
                    “Next” prompt from the system when you’re on the mail step.
                  </li>
                ) : null}
              </ul>
            ) : (
              <p className="text-lab-muted/90">Program data not loaded.</p>
            )}
          </ReportSectionCard>

          {canShowFindings && intake && intake.intake.reviewClaimsCount === 0 && (
            <ReportSectionCard
              title="Credit findings summary"
              description="No review items were surfaced for this file yet. Your program is still working from what was parsed."
            >
              <p className="text-lab-muted/90">You can continue in the guided path or re-check your upload as prompted.</p>
            </ReportSectionCard>
          )}

          {canShowFindings && findingGroups.length > 0 && (
            <ReportSectionCard
              title="Credit findings summary"
              description="What we found, organized by type. This is a reference view, not a dispute list on its own."
            >
              <p className="text-xs text-lab-subtle">
                High-priority first: {findingGroups[0]?.title}. Total items: {intake?.intake.reviewClaimsCount ?? 0}.
              </p>
              <ul className="list-none space-y-3 text-left">
                {findingGroups.slice(0, 6).map((g) => (
                  <li
                    key={g.reviewType ?? g.title}
                    className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3"
                  >
                    <p className="font-medium text-lab-text">{g.title}</p>
                    <p className="text-xs text-lab-subtle">
                      {g.plainLanguageHint ?? g.recommendationLine}
                    </p>
                    <p className="mt-1.5 text-xs text-lab-muted/90">Items: {g.count}</p>
                  </li>
                ))}
              </ul>
              {findingGroups.length > 6 ? (
                <p className="text-xs text-lab-subtle">Additional groups are similar—see the Review step to expand.</p>
              ) : null}
            </ReportSectionCard>
          )}

          {strategy && !strategyPayload && (
            <ReportSectionCard
              title="Recommended disputes"
              description="When strategy is available, you’ll see why the program suggested each item."
            >
              <p className="text-lab-muted/90">Recommendations are not available for this view yet. Continue through Review and Strategy in the main program.</p>
            </ReportSectionCard>
          )}

          {strategyPayload && (
            <>
              <ReportSectionCard
                title="Suggested for this round"
                description="Items the program is prioritizing. Confidence reflects how clear the match is, not a legal outcome."
              >
                {flatItems.filter(
                  (it) => it.recommendation && suggestedIds.has(it.review_claim_id),
                ).length === 0 ? (
                  <p className="text-lab-muted/90">No suggested items, or the round is still being configured.</p>
                ) : (
                  <ul className="list-none space-y-3 text-left">
                    {flatItems
                      .filter((it) => it.recommendation && suggestedIds.has(it.review_claim_id))
                      .map((it) => {
                        const r = it.recommendation!;
                        return (
                          <li
                            key={it.review_claim_id}
                            className="rounded-lg border border-white/[0.08] bg-white/[0.03] p-3"
                          >
                            <p className="font-medium text-lab-text">{r.accountName}</p>
                            <p className="text-xs text-lab-subtle">{labelForReviewType(it.groupType)}</p>
                            {r.why?.short ? (
                              <p className="mt-1.5 text-sm text-lab-muted">{r.why.short}</p>
                            ) : null}
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <span
                                className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${strategyConfidencePillClass(r.confidence.level)}`}
                              >
                                {strategyConfidenceUserLabel(r.confidence.level)}
                              </span>
                              {impactLabel(r.impactLevel) ? (
                                <span className="text-xs text-lab-subtle/90">
                                  {impactLabel(r.impactLevel)}
                                </span>
                              ) : null}
                            </div>
                          </li>
                        );
                      })}
                  </ul>
                )}
              </ReportSectionCard>

              <ReportSectionCard
                title="Other eligible opportunities"
                description="You may or may not have included these in the mailing round."
              >
                {flatItems.filter(
                  (it) => it.recommendation && !suggestedIds.has(it.review_claim_id),
                ).length === 0 ? (
                  <p className="text-lab-muted/90">No other eligible items beyond the suggested set, or the round is still being configured.</p>
                ) : (
                  <ul className="list-none space-y-2.5 text-left text-sm text-lab-muted">
                    {flatItems
                      .filter(
                        (it) => it.recommendation && !suggestedIds.has(it.review_claim_id),
                      )
                      .map((it) => (
                        <li key={it.review_claim_id} className="border-b border-white/[0.04] pb-2 last:border-0 last:pb-0">
                          <span className="text-lab-text/95">{it.recommendation?.accountName}</span> — {it.recommendation?.why?.short}
                        </li>
                      ))}
                  </ul>
                )}
              </ReportSectionCard>
            </>
          )}

          <ReportSectionCard
            title="Letters & execution"
            description="Status only—generate or pay on the main Letters and Payment steps."
          >
            {letters && letters.letters.length > 0 ? (
              <>
                <ul className="list-none space-y-2 text-left text-sm text-lab-muted">
                  <li>
                    <span className="font-medium text-lab-text">Generated: </span> yes ({letters.letters.length}{" "}
                    {letters.letters.length === 1 ? "document" : "documents"})
                  </li>
                  <li>
                    <span className="font-medium text-lab-text">Download: </span> you can download your letters below. Free
                    download is always available when generated—mailing/tracking is an optional add-on in the program.
                  </li>
                </ul>
                <p className="pt-1 text-sm text-lab-text/95">
                  We can mail and track these for you when you use the <Link className="font-medium text-lab-accent" to="/send">Send</Link> and{" "}
                  <Link className="font-medium text-lab-accent" to="/tracking">Tracking</Link> steps.
                </p>
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => void onDownloadBundle()}
                    disabled={downloading}
                    className="inline-flex min-h-[2.5rem] items-center justify-center rounded-md bg-lab-accent px-4 text-sm font-semibold text-zinc-950 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {downloading ? "Preparing…" : "Download letters (text bundle)"}
                  </button>
                  {dlError ? <p className="mt-2 text-xs text-red-300/90">{dlError}</p> : null}
                </div>
                <div className="mt-4 space-y-2 text-left text-sm text-lab-subtle/95">
                  <p className="font-medium text-lab-text/90">Mailing the letters yourself</p>
                  <ol className="ml-4 list-decimal space-y-1.5 text-lab-muted/95">
                    <li>Print your downloaded letters and any supporting text.</li>
                    <li>Include the proof the program asked for, if the mail path required it.</li>
                    <li>Mail to the bureau or company address on each letter.</li>
                    <li>Keep a copy of what you send for your files.</li>
                    <li>Bureaus often follow a 30-day response window; track what comes back in the Responses step.</li>
                  </ol>
                </div>
              </>
            ) : (
              <p className="text-lab-muted/90">Letters are not available yet, or you haven’t generated a package for this round. Continue to Letters when the program brings you there.</p>
            )}
            {payment && (
              <p className="mt-2 text-left text-sm text-lab-muted/90">
                Payment step (this round):{" "}
                {payment.payment.paymentStepCompleted
                  ? "recorded"
                  : payment.payment.onPaymentStep
                    ? "pending on the Payment step"
                    : "not required in this view yet"}
                .{" "}
                <Link to="/payment" className="font-medium text-lab-accent">
                  Open payment
                </Link>{" "}
                if the program sent you there.
              </p>
            )}
            {mail && (
              <div className="mt-3 space-y-1.5 text-left text-sm text-lab-muted/95">
                <p>
                  <span className="font-medium text-lab-text/95">Mailed: </span>
                  {mail.mail.mailedCount > 0
                    ? `${mail.mail.mailedCount} bureau send(s) recorded`
                    : "not mailed through the partner yet"}
                </p>
                {mail.mail.bureauTargets.length > 0 ? (
                  <ul className="list-disc space-y-1 pl-4 text-xs">
                    {mail.mail.bureauTargets.map((b) => (
                      <li key={b.letterId}>
                        {b.bureauDisplay}: {b.sendStatus}
                        {b.trackingNumber ? ` · #${b.trackingNumber}` : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            )}
            {proof && (
              <p className="pt-1 text-left text-sm text-lab-muted/90">
                Proof: ID {proof.proof.hasGovernmentId ? "on file" : "missing"} · address proof{" "}
                {proof.proof.hasAddressProof ? "on file" : "missing"} · signature {proof.proof.hasSignature ? "captured" : "pending"}
                {proof.proof.allRequirementsMet ? " (complete)" : ""}.
              </p>
            )}
            {tracking && (
              <p className="pt-1 text-left text-sm text-lab-muted/90">
                Tracking: {tracking.tracking.mailedBureauCount} bureau mail path(s) recorded,{" "}
                {tracking.tracking.notMailedBureauCount} not mailed yet. Use the Tracking step for
                full detail.
              </p>
            )}
          </ReportSectionCard>

          <ReportSectionCard
            title="Responses & escalation"
            description="Log responses on the main Responses and Escalation pages—this is a summary only."
          >
            {responseMetrics ? (
              <ul className="list-none space-y-2 text-left text-sm text-lab-muted/95">
                <li>Responses on file: {responseMetrics.metrics.totalResponses}</li>
                {responseMetrics.metrics.escalationRecommendedCount > 0 ? (
                  <li>
                    Escalation was suggested for {responseMetrics.metrics.escalationRecommendedCount}{" "}
                    case(s) — use Escalation to review options.
                  </li>
                ) : (
                  <li>No escalation flags from responses yet, or you’re not at that point.</li>
                )}
                {escalation?.escalationLayer?.actions &&
                escalation.escalationLayer.actions.length > 0 ? (
                  <li>Additional escalation actions are available in the program when you’re ready.</li>
                ) : null}
              </ul>
            ) : (
              <p className="text-lab-muted/90">Response metrics will show after the service returns data for this workflow.</p>
            )}
            <p className="pt-1 text-left text-sm">
              <Link to="/responses" className="font-medium text-lab-accent">
                Log responses
              </Link>{" "}
              ·{" "}
              <Link to="/escalation" className="font-medium text-lab-accent">
                Escalation
              </Link>
            </p>
          </ReportSectionCard>
        </motion.div>
      </StepMainColumn>
    </div>
  );
}
