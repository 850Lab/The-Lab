import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
  postCustomerUxEvent,
  postResponseIntake,
} from "@/lib/workflowApi";
import {
  customerPathFromEnvelope,
  isAuthoritativeStepBefore,
} from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const SOURCE_TYPES = [
  { value: "bureau", label: "Credit bureau" },
  { value: "furnisher", label: "Data furnisher" },
  { value: "creditor", label: "Creditor" },
  { value: "collection_agency", label: "Collection agency" },
  { value: "unknown", label: "Not sure" },
] as const;

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
        Escalation guidance
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
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[34%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-28 pt-24 sm:px-6 sm:pb-32 sm:pt-28">
        <p className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle">
          After mail
        </p>
        <h1 className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text">
          Bureau &amp; furnisher responses
        </h1>
        <p className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted">
          After mail goes out, bureaus may reply by mail or online. Summarize what you received in
          your own words — we classify the response and show your next step (same rules as the main
          app).
        </p>

        <div className="mt-4 text-center">
          <Link
            to="/tracking"
            className="text-sm font-medium text-lab-accent hover:text-sky-300"
          >
            ← Back to tracking
          </Link>
        </div>

        {pageLoading ? (
          <p className="mt-10 text-center text-sm text-lab-muted">Loading responses…</p>
        ) : loadError ? (
          <div className="mt-10 space-y-3 rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-4">
            <p className="text-sm text-amber-200/95">{loadError}</p>
            <button
              type="button"
              onClick={() => void loadList()}
              className="text-sm font-medium text-lab-accent"
            >
              Try again
            </button>
          </div>
        ) : (
          <>
            <motion.form
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              onSubmit={handleSubmit}
              className="mt-10 space-y-4 rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 sm:px-6"
            >
              <h2 className="text-[15px] font-semibold text-lab-text">Add a response</h2>

              <div>
                <label htmlFor="resp-source" className="text-xs text-lab-subtle">
                  Who sent this?
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
                  What does it say? (at least 8 characters)
                </label>
                <textarea
                  id="resp-summary"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                  rows={5}
                  placeholder="Example: Equifax says they verified the account as accurate and will not delete it."
                  className="mt-1 w-full resize-y rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
                />
              </div>

              <div>
                <label htmlFor="resp-kw" className="text-xs text-lab-subtle">
                  Key phrases (optional, comma-separated)
                </label>
                <input
                  id="resp-kw"
                  type="text"
                  value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                  placeholder="verified, deleted, investigation complete"
                  className="mt-1 w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
                />
              </div>

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

              <button
                type="submit"
                disabled={submitBusy || !summaryOk}
                className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {submitBusy ? "Submitting…" : "Submit & classify"}
              </button>
            </motion.form>

            {guidance ? (
              <div
                className={`mt-8 rounded-xl border px-4 py-4 sm:px-5 ${
                  guidance.primaryState === "escalation_available"
                    ? "border-sky-500/30 bg-sky-500/[0.08]"
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
                    className="mt-3 inline-flex text-sm font-semibold text-lab-accent hover:text-sky-300"
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

            <section className="mt-10">
              <h2 className="text-sm font-semibold text-lab-text">Your submitted responses</h2>
              {rows.length === 0 ? (
                <p className="mt-3 text-sm leading-relaxed text-lab-muted">
                  No responses logged yet. When a bureau or furnisher writes back, add a short
                  summary above — we classify it and update guidance. If nothing has arrived yet,
                  check Tracking for send status.
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
          </>
        )}
      </main>
    </div>
  );
}
