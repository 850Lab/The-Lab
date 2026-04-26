import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type {
  CustomerResponseRow,
  ResponseFlowGuidance,
  ResponseFlowMetrics,
  ResponseIntakeSubmitResponse,
} from "@/lib/responseTypes";
import {
  fetchWorkflowResponseMetrics,
  fetchWorkflowResponses,
  postBeginNextDisputeRound,
  postCustomerUxEvent,
  postResponseIntake,
} from "@/lib/workflowApi";
import {
  customerPathFromEnvelope,
  isAuthoritativeStepBefore,
} from "@/lib/workflowStepRoutes";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  orionNarrativeCoherent,
  orionStepHeroCopy,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import {
  easeStep,
  stepChildVariants as headerVariants,
  stepPageVariants as pageVariants,
} from "@/lib/motionStep";

const SOURCE_TYPES = [
  { value: "bureau", label: "Credit bureau" },
  { value: "furnisher", label: "Furnisher / data provider" },
  { value: "creditor", label: "Creditor" },
  { value: "collection_agency", label: "Collection agency" },
  { value: "unknown", label: "Not sure — pick the closest match" },
] as const;

function ResponseProgressStrip({ hasLoggedResponse }: { hasLoggedResponse: boolean }) {
  const step2Done = hasLoggedResponse;
  const step3Active = hasLoggedResponse;

  return (
    <motion.div
      variants={headerVariants}
      className="surface-where-fits mx-auto mt-6 max-w-2xl"
    >
      <p className="text-center text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
        Where this fits
      </p>
      <ol className="mt-3 flex flex-col gap-2 text-sm sm:mt-4 sm:flex-row sm:justify-center sm:gap-3 sm:text-[13px]">
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted">
          <span className="font-semibold text-emerald-200/95">1.</span>
          <span className="ml-1.5">Tracking in progress</span>
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
          <span className="ml-1.5">Response logged</span>
        </li>
        <li
          className={
            step3Active
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted"
          }
        >
          <span className={step3Active ? "text-lab-accent" : "text-lab-subtle"}>3.</span>
          <span className="ml-1.5">Next action decided later</span>
        </li>
      </ol>
    </motion.div>
  );
}

function ResponseRoundContinuityModule({
  loggedCount,
}: {
  loggedCount: number;
}) {
  return (
    <div className="surface-round-continuity">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-lab-subtle">
        Your current round
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        This step is for updates that come back after you mailed — mail, online, or portal. When
        something meaningful arrives, record it here. After you save it, the program can better
        suggest what may need to happen next.
      </p>
      {loggedCount > 0 ? (
        <p className="mt-2 text-xs text-lab-subtle">
          You&apos;ve logged {loggedCount} response{loggedCount === 1 ? "" : "s"} in this program so
          far.
        </p>
      ) : null}
    </div>
  );
}

const RESPONSE_INTAKE_HERO_FALLBACK = {
  title: "Record a bureau or furnisher response for this round",
  subtitle:
    "Use this page when you receive a meaningful mail update, letter, or portal response related to the round you already sent. Logging it here helps keep your progress clear and supports the next decision.",
} as const;

function summaryLengthBucket(text: string): string {
  const n = text.trim().length;
  if (n < 8) return "lt_8";
  if (n < 32) return "lt_32";
  if (n <= 200) return "m_32_200";
  return "gt_200";
}

function formatReceivedAt(iso: string): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(t));
}

function EscalationBlock({ esc }: { esc: CustomerResponseRow["escalationRecommendation"] }) {
  if (!esc || typeof esc !== "object" || !Object.keys(esc).length) return null;
  const primary = esc.primary_path;
  const reason = esc.reasoning_safe;
  const priority = esc.priority;
  return (
    <div className="mt-3 rounded-lg border border-white/[0.08] bg-lab-bg/80 px-3 py-2 text-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
        Suggested next steps
      </p>
      {primary ? (
        <p className="mt-1 font-medium text-lab-text">
          Suggested path: <span className="text-lab-accent">{primary}</span>
          {priority ? (
            <span className="ml-2 text-xs font-normal text-lab-muted">({priority})</span>
          ) : null}
        </p>
      ) : null}
      {reason ? (
        <p className="mt-2 leading-relaxed text-lab-muted">{reason}</p>
      ) : null}
      {esc.factors && esc.factors.length > 0 ? (
        <p className="mt-2 text-xs text-lab-subtle">
          Factors: {esc.factors.join(", ")}
        </p>
      ) : null}
    </div>
  );
}

export function ResponseIntakePage() {
  const navigate = useNavigate();
  const {
    token,
    workflowId,
    envelope,
    authoritativeStepId,
    applyWorkflowEnvelope,
    orionViewModel,
    integrityHints,
  } = useCustomerWorkflow();

  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rows, setRows] = useState<CustomerResponseRow[]>([]);
  const [metrics, setMetrics] = useState<ResponseFlowMetrics | null>(null);
  const [guidance, setGuidance] = useState<ResponseFlowGuidance | null>(null);

  const [sourceType, setSourceType] = useState<string>("bureau");
  const [summary, setSummary] = useState("");
  const [keywords, setKeywords] = useState("");
  const [submitBusy, setSubmitBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ResponseIntakeSubmitResponse | null>(null);
  const [outcomesJson, setOutcomesJson] = useState("");
  const [beginNextBusy, setBeginNextBusy] = useState(false);
  const [beginNextError, setBeginNextError] = useState<string | null>(null);

  const overallComplete =
    (envelope?.workflowState?.overallStatus ?? "").toLowerCase() === "completed";

  const orionAuthority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const responseIntakeHero = useMemo(
    () => orionStepHeroCopy(orionAuthority, orionViewModel, RESPONSE_INTAKE_HERO_FALLBACK),
    [orionAuthority, orionViewModel],
  );

  const responseCoherent = useMemo(
    () => orionNarrativeCoherent(orionAuthority, orionViewModel),
    [orionAuthority, orionViewModel],
  );

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

  const correlationRef = useRef<string>(
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `ux_${Date.now()}`,
  );

  const uxBase = useCallback(
    () => ({ correlation_id: correlationRef.current }),
    [],
  );

  useEffect(() => {
    if (!token || !workflowId) return;
    void postCustomerUxEvent(token, workflowId, {
      event_name: "response_intake_page_viewed",
      metadata: uxBase(),
    }).catch(() => {});
  }, [token, workflowId, uxBase]);

  const loadList = useCallback(async () => {
    if (!token || !workflowId) {
      setRows([]);
      setLoadError(null);
      setPageLoading(false);
      return;
    }
    setPageLoading(true);
    setLoadError(null);
    try {
      const [listRes, metricsRes] = await Promise.allSettled([
        fetchWorkflowResponses(token, workflowId),
        fetchWorkflowResponseMetrics(token, workflowId),
      ]);
      if (listRes.status === "rejected") {
        throw listRes.reason;
      }
      const data = listRes.value;
      applyWorkflowEnvelope(data.workflow);
      setRows(data.responses);
      if (metricsRes.status === "fulfilled") {
        setMetrics(metricsRes.value.metrics);
        setGuidance(metricsRes.value.guidance);
      } else {
        setMetrics(null);
        setGuidance(null);
      }
      void postCustomerUxEvent(token, workflowId, {
        event_name: "response_history_viewed",
        metadata: {
          ...uxBase(),
          response_count: data.responses.length,
        },
      }).catch(() => {});
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setRows([]);
      setMetrics(null);
      setGuidance(null);
      void postCustomerUxEvent(token, workflowId, {
        event_name: "response_list_fetch_failed",
        status: "error",
        metadata: uxBase(),
      }).catch(() => {});
    } finally {
      setPageLoading(false);
    }
  }, [token, workflowId, applyWorkflowEnvelope, uxBase]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  useEffect(() => {
    if (pageLoading || loadError) return;
    if (!envelope) return;
    if (!authoritativeStepId) return;
    if (isAuthoritativeStepBefore(authoritativeStepId, "track")) {
      navigate(customerPathFromEnvelope(envelope), { replace: true });
    }
  }, [pageLoading, loadError, envelope, authoritativeStepId, navigate]);

  const summaryOk = useMemo(() => summary.trim().length >= 8, [summary]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !workflowId || !summaryOk) return;
    setSubmitError(null);
    setLastResult(null);
    let claimOutcomes: Record<string, string> | undefined;
    if (outcomesJson.trim()) {
      try {
        const parsed = JSON.parse(outcomesJson) as unknown;
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
          setSubmitError("Per-item outcomes must be a JSON object, e.g. {\"claim_id\": \"verified\"}.");
          return;
        }
        claimOutcomes = {};
        for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
          const key = String(k).trim();
          if (!key) continue;
          claimOutcomes[key] = String(v).trim().toLowerCase();
        }
      } catch {
        setSubmitError("Could not parse per-item outcomes JSON.");
        return;
      }
    }
    setSubmitBusy(true);
    void postCustomerUxEvent(token, workflowId, {
      event_name: "response_intake_submit_attempted",
      metadata: {
        ...uxBase(),
        source_type: sourceType,
        summary_length_bucket: summaryLengthBucket(summary),
        has_keywords: keywords.trim().length > 0,
      },
    }).catch(() => {});
    try {
      const kw = keywords
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const parsed_summary: Record<string, unknown> = {
        summary_safe: summary.trim(),
      };
      if (kw.length) parsed_summary.outcome_keywords = kw;
      const r = await postResponseIntake(token, workflowId, {
        source_type: sourceType,
        response_channel: "manual_entry",
        parsed_summary,
      });
      applyWorkflowEnvelope(r.workflow);
      setLastResult(r);
      setSummary("");
      setKeywords("");
      await loadList();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitBusy(false);
    }
  };

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
        {pageLoading ? (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="mt-10 text-center text-sm text-lab-muted"
          >
            Loading responses…
          </motion.p>
        ) : loadError ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="mt-10 space-y-3 rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-4"
          >
            <p className="text-sm text-amber-200/95">{loadError}</p>
            <button
              type="button"
              onClick={() => void loadList()}
              className="text-sm font-medium text-lab-accent"
            >
              Try again
            </button>
          </motion.div>
        ) : (
          <motion.div
            variants={pageVariants}
            initial="hidden"
            animate="show"
            className="pb-4"
          >
            <motion.h2
              variants={headerVariants}
              className="step-title"
            >
              {responseIntakeHero.title}
            </motion.h2>
            <motion.p
              variants={headerVariants}
              className="step-support"
            >
              {responseIntakeHero.subtitle}
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
                  <span>This step is only for meaningful responses or updates</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>You do not need to log every quiet day</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>You can return to Tracking anytime to keep watching progress</span>
                </li>
              </ul>
            </motion.div>

            <ResponseProgressStrip hasLoggedResponse={rows.length > 0} />

            <motion.div variants={headerVariants} className="mx-auto mt-6 max-w-lg">
              <ResponseRoundContinuityModule loggedCount={rows.length} />
            </motion.div>

            <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-lg">
              <ProgramFlowBridge>
                {responseCoherent ? (
                  <>
                    <span className="font-medium text-lab-text">Log meaningful replies here</span> — when
                    something real arrives after tracking; skip quiet days. Same program, same round.
                  </>
                ) : (
                  <>
                    <span className="font-medium text-lab-text">After tracking starts,</span> use this
                    when something real comes back — not for every quiet day. The same program keeps your
                    round together.
                  </>
                )}
              </ProgramFlowBridge>
            </motion.div>

            {!responseCoherent ? (
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-4 max-w-lg text-center text-xs leading-relaxed text-lab-subtle sm:text-sm"
              >
                If you&apos;re not sure how to label something, choose the closest match. You can
                record the key details without writing everything perfectly — it helps keep the round
                accurate as new information arrives.
              </motion.p>
            ) : null}

            <motion.div
              variants={headerVariants}
              className="mx-auto mt-8 max-w-lg rounded-xl border border-white/[0.08] bg-lab-surface/50 px-4 py-4 sm:px-5 sm:py-5"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-lab-subtle">
                What should be logged here?
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-relaxed text-lab-muted">
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>A mailed response from a bureau</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>A furnisher reply</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>A meaningful portal or account update tied to this round</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>A notice that changes what happens next</span>
                </li>
              </ul>
              <p className="mt-4 text-xs font-semibold uppercase tracking-[0.1em] text-lab-subtle">
                What does not need to be logged?
              </p>
              <ul className="mt-2 space-y-1.5 text-sm text-lab-subtle">
                <li>Ordinary waiting time</li>
                <li>No-update days or routine silence after mailing</li>
              </ul>
            </motion.div>

            {rows.length === 0 ? (
              <motion.div
                variants={headerVariants}
                className="mx-auto mt-6 max-w-lg rounded-xl border border-white/[0.1] bg-lab-bg/60 px-4 py-4 text-center sm:px-5"
              >
                <p className="text-sm font-medium text-lab-text">You may not need this page yet</p>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                  Come here once you receive a meaningful update tied to your mailed round. Until
                  then,{" "}
                  <Link className="font-medium text-lab-accent hover:text-zinc-100" to="/tracking">
                    Tracking
                  </Link>{" "}
                  is the right place to monitor progress.
                </p>
              </motion.div>
            ) : null}

            <div className="mt-6 text-center">
              <Link
                to="/tracking"
                className="text-sm font-medium text-lab-accent hover:text-zinc-100"
              >
                Return to Tracking
              </Link>
              <p className="mt-2 text-xs text-lab-subtle">
                You can monitor this round anytime in Tracking.
              </p>
            </div>

            <motion.form
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              onSubmit={handleSubmit}
              className="mt-10 space-y-4 rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 sm:px-6"
            >
              <h2 className="text-[15px] font-semibold text-lab-text">Log an update</h2>

              <div>
                <label htmlFor="resp-source" className="text-xs text-lab-subtle">
                  Who sent the response?
                </label>
                <select
                  id="resp-source"
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text"
                >
                  {SOURCE_TYPES.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="resp-summary" className="text-xs text-lab-subtle">
                  What kind of update did you receive?
                </label>
                <p className="mt-1 text-xs text-lab-subtle">
                  Add the letter or note details in your own words (at least 8 characters).
                </p>
                <textarea
                  id="resp-summary"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  rows={5}
                  placeholder="Example: Equifax says they verified the account as accurate and will not delete it."
                  className="mt-2 w-full resize-y rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
                />
              </div>

              <div>
                <label htmlFor="resp-kw" className="text-xs text-lab-subtle">
                  Keywords (optional, comma-separated)
                </label>
                <p className="mt-1 text-xs text-lab-subtle">
                  Short phrases that help describe the update — not required.
                </p>
                <input
                  id="resp-kw"
                  type="text"
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                  placeholder="verified, deleted, investigation complete"
                  className="mt-2 w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
                />
              </div>

              <details className="details-calm rounded-lg border border-white/[0.08] bg-lab-bg/40 px-3 py-2">
                <summary className="cursor-pointer list-none text-xs font-medium text-lab-muted [&::-webkit-details-marker]:hidden">
                  Advanced: per-item outcomes (optional JSON) ▾
                </summary>
                <label htmlFor="resp-outcomes" className="mt-3 block text-xs text-lab-subtle">
                  Only if you need to map specific items — same format as before.
                </label>
                <textarea
                  id="resp-outcomes"
                  value={outcomesJson}
                  onChange={(e) => setOutcomesJson(e.target.value)}
                  rows={2}
                  placeholder='{"review_claim_id": "deleted"} — values: deleted, updated, verified, no_response'
                  className="mt-2 w-full resize-y rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 font-mono text-xs text-lab-text placeholder:text-lab-subtle"
                />
              </details>

              {submitError ? (
                <p className="text-sm text-red-300/95">{submitError}</p>
              ) : null}

              {lastResult?.warning ? (
                <p className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-sm text-amber-100/95">
                  {lastResult.warning.messageSafe}
                </p>
              ) : null}

              {lastResult?.classification ? (
                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-3 text-sm">
                  <p className="text-xs font-medium uppercase text-lab-subtle">
                    Latest result
                  </p>
                  <p className="mt-1 font-medium text-lab-text">
                    {lastResult.classification.label}
                  </p>
                  <p className="mt-2 leading-relaxed text-lab-muted">
                    {lastResult.classification.reasoningSafe}
                  </p>
                  <p className="mt-2 text-xs text-lab-subtle">
                    Next: {lastResult.classification.recommendedNextAction} · Confidence{" "}
                    {lastResult.classification.confidence != null
                      ? `${Math.round(lastResult.classification.confidence * 100)}%`
                      : "—"}
                  </p>
                  {lastResult.escalationRecommendation ? (
                    <EscalationBlock esc={lastResult.escalationRecommendation} />
                  ) : null}
                </div>
              ) : null}

              <div className="space-y-2 border-t border-white/[0.06] pt-4">
                <p className="text-center text-sm font-semibold text-lab-text">Ready to save this update?</p>
                <p className="text-center text-xs leading-relaxed text-lab-muted">
                  Once you log it, this round will have a clearer record of what came back and what may
                  need to happen next.
                </p>
                <button
                  type="submit"
                  disabled={submitBusy || !summaryOk}
                  className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {submitBusy ? "Saving…" : "Save response"}
                </button>
                <p className="text-center text-xs text-lab-subtle">
                  You can return to Tracking after saving.
                </p>
              </div>
            </motion.form>

            {guidance ? (
              <div
                className={`mt-8 rounded-xl border px-4 py-4 sm:px-5 ${
                  guidance.primaryState === "escalation_available"
                    ? "border-zinc-600/40 bg-zinc-500/[0.08]"
                    : guidance.primaryState === "classification_issues_present"
                      ? "border-amber-500/25 bg-amber-500/[0.07]"
                      : "border-white/[0.1] bg-lab-surface/95"
                }`}
              >
                <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                  Next step
                </p>
                <p className="mt-2 text-[15px] font-semibold text-lab-text">{guidance.title}</p>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">{guidance.message}</p>
                {guidance.actionTarget && guidance.actionLabel ? (
                  <Link
                    to={guidance.actionTarget}
                    className="mt-3 inline-flex text-sm font-semibold text-lab-accent hover:text-zinc-100"
                  >
                    {guidance.actionLabel} →
                  </Link>
                ) : null}
              </div>
            ) : null}

            {metrics && metrics.totalResponses > 0 ? (
              <div className="mt-8 rounded-xl border border-white/[0.08] bg-lab-surface/90 px-4 py-3 sm:px-5">
                <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                  Summary
                </p>
                <ul className="mt-2 space-y-1.5 text-sm text-lab-muted">
                  <li>
                    <span className="text-lab-text">Responses received:</span>{" "}
                    {metrics.totalResponses}
                  </li>
                  <li>
                    <span className="text-lab-text">Classified successfully:</span>{" "}
                    {metrics.classifiedSuccessCount}
                    {metrics.classifiedFailureCount > 0 ? (
                      <span className="text-lab-subtle">
                        {" "}
                        ({metrics.classifiedFailureCount} failed)
                      </span>
                    ) : null}
                  </li>
                  <li>
                    <span className="text-lab-text">Escalation recommended:</span>{" "}
                    {metrics.escalationRecommendedCount}
                  </li>
                  {metrics.latestResponseAt ? (
                    <li>
                      <span className="text-lab-text">Latest response:</span>{" "}
                      {formatReceivedAt(metrics.latestResponseAt)}
                    </li>
                  ) : null}
                </ul>
              </div>
            ) : null}

            {overallComplete ? (
              <div className="surface-emerald-reassure mt-10">
                <h2 className="text-[15px] font-semibold text-lab-text sm:text-base">
                  Next phase: another dispute round
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                  Continue in the same program when you are ready to re-dispute unresolved items.
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
              </div>
            ) : null}

            <section className="mt-10">
              <h2 className="text-sm font-semibold text-lab-text">Your submitted responses</h2>
              {rows.length === 0 ? (
                <p className="mt-3 text-sm leading-relaxed text-lab-muted">
                  Nothing saved yet. When mail or a portal update arrives, use the form above — we
                  help classify it and update guidance. Delivery updates stay in{" "}
                  <Link className="font-medium text-lab-accent hover:text-zinc-100" to="/tracking">
                    Tracking
                  </Link>
                  .
                </p>
              ) : (
                <ul className="mt-4 space-y-4">
                  {rows.map((r) => (
                    <li
                      key={r.responseId}
                      className="rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-4"
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <span className="text-xs text-lab-subtle">
                          {formatReceivedAt(r.receivedAt)}
                        </span>
                        <span className="text-xs font-medium uppercase text-lab-muted">
                          {r.classificationStatus}
                        </span>
                      </div>
                      <p className="mt-2 text-sm font-medium text-lab-text">
                        {r.classification ?? "—"}
                      </p>
                      {r.summarySafePreview ? (
                        <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-lab-muted">
                          {r.summarySafePreview}
                        </p>
                      ) : null}
                      {r.reasoningSafe ? (
                        <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                          {r.reasoningSafe}
                        </p>
                      ) : null}
                      {r.recommendedNextAction ? (
                        <p className="mt-2 text-xs text-lab-subtle">
                          Suggested next: {r.recommendedNextAction}
                        </p>
                      ) : null}
                      <EscalationBlock esc={r.escalationRecommendation} />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </motion.div>
        )}
      </StepMainColumn>
    </div>
  );
}
