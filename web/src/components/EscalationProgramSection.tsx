import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import type { ProgramEscalationPayload } from "@/lib/escalationProgramTypes";
import { postEscalationUxState } from "@/lib/workflowApi";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";

function actionTypeLabel(t: string): string {
  switch (t) {
    case "method_of_verification":
      return "Method of verification";
    case "furnisher_dispute":
      return "Furnisher dispute";
    case "cfpb_complaint":
      return "CFPB complaint draft";
    case "call_script":
      return "Call script";
    default:
      return t.replace(/_/g, " ");
  }
}

type Props = {
  program: ProgramEscalationPayload;
  token: string;
  workflowId: string;
  applyWorkflowEnvelope: (env: WorkflowEnvelope) => void;
  onUpdated?: () => void;
};

export function EscalationProgramSection({
  program,
  token,
  workflowId,
  applyWorkflowEnvelope,
  onUpdated,
}: Props) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const patch = useCallback(
    async (actionId: string, reviewed: boolean, proceeded: boolean) => {
      setErr(null);
      setBusyId(actionId);
      try {
        const r = await postEscalationUxState(token, workflowId, {
          actionId,
          reviewed,
          proceeded,
        });
        applyWorkflowEnvelope(r.workflow);
        onUpdated?.();
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setBusyId(null);
      }
    },
    [token, workflowId, applyWorkflowEnvelope, onUpdated],
  );

  if (!program.groups?.length) return null;

  return (
    <section className="mt-8 space-y-6 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] px-4 py-5 sm:px-5">
      <div className="border-b border-amber-500/15 pb-4">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-200/90">
          Same program · Extra leverage
        </p>
        <h2 className="mt-1.5 text-lg font-semibold tracking-tight text-lab-text">
          When bureau outcomes stall
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-lab-muted">{program.continueProgramNote}</p>
        <p className="mt-2 text-xs leading-relaxed text-lab-subtle">{program.differentiationNote}</p>
      </div>

      <div className="rounded-lg border border-white/[0.08] bg-lab-surface/60 px-3 py-2.5 text-xs text-lab-muted">
        <span className="font-semibold text-lab-text">Next dispute round</span> (below) is your in-app
        letter cycle. This section is <span className="font-medium text-lab-text">parallel</span>{" "}
        paperwork and calls you can start anytime.
      </div>

      {err ? <p className="text-sm text-red-300/90">{err}</p> : null}

      {program.groups.map((g) => (
        <div key={g.triggerKey} className="space-y-3">
          <div>
            <h3 className="text-base font-semibold text-lab-text">{g.triggerLabel}</h3>
            <p className="mt-1 text-sm leading-relaxed text-lab-muted">{g.why}</p>
          </div>
          <ul className="space-y-3">
            {g.actions.map((a) => {
              const expanded = openId === a.id;
              const busy = busyId === a.id;
              return (
                <li
                  key={a.id}
                  className="rounded-xl border border-white/[0.1] bg-lab-bg/80 px-3 py-3.5 sm:px-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-accent">
                        {actionTypeLabel(a.type)}
                      </p>
                      <p className="mt-0.5 font-medium text-lab-text">{a.title}</p>
                      {a.summarySafe ? (
                        <p className="mt-1.5 text-sm leading-relaxed text-lab-muted">{a.summarySafe}</p>
                      ) : null}
                    </div>
                    <Link
                      to={`/escalation-action?action=${encodeURIComponent(a.id)}`}
                      className="shrink-0 text-xs font-semibold text-lab-accent hover:text-sky-300"
                    >
                      Full screen →
                    </Link>
                  </div>

                  {a.affectedItems && a.affectedItems.length > 0 ? (
                    <ul className="mt-2 space-y-1 border-t border-white/[0.06] pt-2 text-xs text-lab-muted">
                      {a.affectedItems.map((it) => (
                        <li key={it.reviewClaimId} className="leading-relaxed">
                          <span className="font-mono text-[10px] text-lab-subtle">{it.reviewClaimId}</span>
                          {" · "}
                          {it.line}
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => setOpenId(expanded ? null : a.id)}
                      className="rounded-lg border border-white/[0.12] px-3 py-1.5 text-xs font-semibold text-lab-text hover:bg-white/[0.04] disabled:opacity-50"
                    >
                      {expanded ? "Hide draft" : "Show letter / draft"}
                    </button>
                    <button
                      type="button"
                      disabled={busy || a.userMarkedReviewed}
                      onClick={() => void patch(a.id, true, false)}
                      className="rounded-lg border border-white/[0.12] px-3 py-1.5 text-xs font-semibold text-lab-muted hover:bg-white/[0.04] disabled:opacity-50"
                    >
                      {a.userMarkedReviewed ? "Reviewed" : "Mark reviewed"}
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void patch(a.id, false, true)}
                      className="rounded-lg border border-lab-accent/40 bg-lab-accent/10 px-3 py-1.5 text-xs font-semibold text-lab-accent hover:bg-lab-accent/15 disabled:opacity-50"
                    >
                      {a.userMarkedProceeded ? "Proceeding ✓" : "I’m taking this action"}
                    </button>
                  </div>

                  {expanded && a.documentDraft?.trim() ? (
                    <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-white/[0.08] bg-black/30 p-3 text-[11px] leading-relaxed text-lab-muted">
                      {a.documentDraft}
                    </pre>
                  ) : null}

                  {expanded && a.callBullets && a.callBullets.length > 0 ? (
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-lab-muted">
                      {a.callBullets.map((b, i) => (
                        <li key={i}>{b}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ))}

      <p className="text-center text-[11px] text-lab-subtle">
        <Link to="/escalation" className="font-semibold text-lab-accent hover:text-sky-300">
          Open full escalation toolkit →
        </Link>
      </p>
    </section>
  );
}
