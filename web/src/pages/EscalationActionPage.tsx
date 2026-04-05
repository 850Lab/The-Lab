import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type { EscalationLeverageAction } from "@/lib/escalationLayerTypes";
import type { ProgramEscalationActionRow } from "@/lib/escalationProgramTypes";
import { fetchEscalationLayer } from "@/lib/workflowApi";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const FALLBACK_ID = "follow_up_letter";

export function EscalationActionPage() {
  const [searchParams] = useSearchParams();
  const actionId = searchParams.get("action")?.trim() || FALLBACK_ID;
  const { token, workflowId, applyWorkflowEnvelope, loading: ctxLoading } = useCustomerWorkflow();
  const [action, setAction] = useState<EscalationLeverageAction | null>(null);
  const [programAction, setProgramAction] = useState<ProgramEscalationActionRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token || !workflowId) {
      setAction(null);
      setProgramAction(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    void fetchEscalationLayer(token, workflowId)
      .then((r) => {
        applyWorkflowEnvelope(r.workflow);
        let pa: ProgramEscalationActionRow | null = null;
        const groups = r.escalationLayer.programEscalation?.groups;
        if (groups) {
          for (const g of groups) {
            const hit = g.actions.find((x) => x.id === actionId);
            if (hit) {
              pa = hit;
              break;
            }
          }
        }
        setProgramAction(pa);
        const found = r.escalationLayer.actions.find((a) => a.id === actionId);
        setAction(found ?? (pa ? null : r.escalationLayer.actions[0] ?? null));
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setAction(null);
        setProgramAction(null);
      })
      .finally(() => setLoading(false));
  }, [token, workflowId, actionId, applyWorkflowEnvelope]);

  const title = useMemo(
    () => programAction?.title ?? action?.title ?? "Escalation step",
    [programAction, action],
  );

  const [copied, setCopied] = useState(false);
  const copyScript = useCallback(async () => {
    const t = action?.callScript?.trim();
    if (!t) return;
    try {
      await navigator.clipboard.writeText(t);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* ignore */
    }
  }, [action]);

  return (
    <div className="min-h-full bg-lab-bg">
      <TopBarMinimal />
      <main className="mx-auto max-w-md px-4 pb-20 pt-24 sm:max-w-lg sm:px-6 sm:pt-28">
        {!ctxLoading && (!token || !workflowId) ? (
          <p className="mt-6 text-sm text-lab-muted">
            Sign in with your program open to load this checklist.
          </p>
        ) : null}
        {ctxLoading || (token && workflowId) ? (
          <>
        <p className="text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle">
          Your leverage
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-lab-text">{title}</h1>

        {loading ? (
          <p className="mt-6 text-sm text-lab-muted">Loading checklist…</p>
        ) : error ? (
          <p className="mt-6 text-sm text-amber-200/95">{error}</p>
        ) : action || programAction ? (
          <div className="mt-6 space-y-5">
            <p className="text-sm leading-relaxed text-lab-muted">
              {programAction?.summarySafe ?? action?.tagline ?? action?.whyNow ?? ""}
            </p>
            {action?.whyNow && (!programAction?.summarySafe || action.whyNow !== programAction.summarySafe) ? (
              <p className="text-sm leading-relaxed text-lab-text">{action.whyNow}</p>
            ) : null}
            {programAction?.affectedItems && programAction.affectedItems.length > 0 ? (
              <div>
                <h2 className="text-sm font-semibold text-lab-text">Affected items</h2>
                <ul className="mt-2 space-y-1 text-sm text-lab-muted">
                  {programAction.affectedItems.map((it) => (
                    <li key={it.reviewClaimId} className="leading-relaxed">
                      <span className="font-mono text-xs text-lab-subtle">{it.reviewClaimId}</span> —{" "}
                      {it.line}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {programAction?.documentDraft?.trim() ? (
              <div className="rounded-xl border border-white/[0.1] bg-lab-surface/90 px-4 py-4">
                <h2 className="text-sm font-semibold text-lab-text">Letter / complaint draft</h2>
                <p className="mt-1 text-xs text-lab-subtle">
                  Edit placeholders, then mail or paste into a complaint form. Not legal advice.
                </p>
                <pre className="mt-3 max-h-[min(50vh,420px)] overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-lab-muted">
                  {programAction.documentDraft}
                </pre>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(programAction.documentDraft ?? "");
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    } catch {
                      /* ignore */
                    }
                  }}
                  className="mt-3 rounded-lg border border-white/[0.12] px-3 py-2 text-xs font-semibold text-lab-accent"
                >
                  {copied ? "Copied" : "Copy draft"}
                </button>
                {programAction.type === "cfpb_complaint" ? (
                  <a
                    href="https://www.consumerfinance.gov/complaint/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 inline-block text-xs font-semibold text-lab-accent hover:text-sky-300"
                  >
                    Open CFPB complaint site ↗
                  </a>
                ) : null}
              </div>
            ) : null}
            {programAction?.callBullets && programAction.callBullets.length > 0 ? (
              <div className="rounded-xl border border-white/[0.1] bg-lab-surface/90 px-4 py-4">
                <h2 className="text-sm font-semibold text-lab-text">Call talking points</h2>
                <ul className="mt-2 list-disc space-y-2 pl-5 text-sm text-lab-muted">
                  {programAction.callBullets.map((b, i) => (
                    <li key={i}>{b}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {action ? (
              <div>
                <h2 className="text-sm font-semibold text-lab-text">Checklist</h2>
                <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-lab-muted">
                  {action.steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </div>
            ) : null}
            {action?.callScript?.trim() ? (
              <div className="rounded-xl border border-white/[0.1] bg-lab-surface/90 px-4 py-4">
                <h2 className="text-sm font-semibold text-lab-text">Call script</h2>
                <p className="mt-2 text-sm leading-relaxed text-lab-muted">{action.callScript}</p>
                <button
                  type="button"
                  onClick={() => void copyScript()}
                  className="mt-3 rounded-lg border border-white/[0.12] px-3 py-2 text-xs font-semibold text-lab-accent"
                >
                  {copied ? "Copied" : "Copy script"}
                </button>
              </div>
            ) : null}
            {action && action.links.length > 0 ? (
              <div>
                <h2 className="text-sm font-semibold text-lab-text">Links</h2>
                <ul className="mt-2 space-y-2">
                  {action.links.map((l) => (
                    <li key={l.url}>
                      <a
                        href={l.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-lab-accent hover:text-sky-300"
                      >
                        {l.label} ↗
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="mt-6 text-sm text-lab-muted">No action details available.</p>
        )}


        <div className="mt-10 flex flex-col gap-3">
          <Link
            to="/escalation"
            className="text-center text-sm font-semibold text-lab-accent hover:text-sky-300"
          >
            ← Back to full escalation toolkit
          </Link>
          <Link to="/responses" className="text-center text-sm text-lab-muted hover:text-lab-text">
            Record another bureau response
          </Link>
        </div>

        <p className="mt-10 text-center text-[11px] text-lab-subtle">
          Educational only — not legal advice.
        </p>
          </>
        ) : null}
      </main>
    </div>
  );
}
