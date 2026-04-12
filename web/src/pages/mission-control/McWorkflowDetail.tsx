import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import {
  mccFetchWorkflowEvents,
  mccGet,
  getMissionControlAdminKey,
  type McWorkflowEventRow,
} from "@/lib/missionControlApi";
import { McStatusChip } from "@/components/mission-control/McStatusChip";
import { McWorkflowOperatorPanel } from "@/components/mission-control/McWorkflowOperatorPanel";

export function McWorkflowDetail() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const location = useLocation();
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [events, setEvents] = useState<McWorkflowEventRow[]>([]);
  const [eventsErr, setEventsErr] = useState<string | null>(null);

  const loadDetail = useCallback(async () => {
    if (!workflowId || !getMissionControlAdminKey()) return;
    setErr(null);
    setEventsErr(null);
    try {
      const d = await mccGet<Record<string, unknown>>(
        `/internal/admin/mission-control/workflows/${workflowId}`,
      );
      setData(d);
      if (d && typeof d === "object" && d.ok === true) {
        try {
          setEvents(await mccFetchWorkflowEvents(workflowId));
        } catch (e) {
          setEventsErr(String((e as Error).message || e));
          setEvents([]);
        }
      } else {
        setEvents([]);
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }, [workflowId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    if (location.hash !== "#operator-actions" || !data?.ok) return;
    const el = document.getElementById("operator-actions");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [location.hash, data?.ok]);

  if (!getMissionControlAdminKey()) {
    return <p className="text-lab-muted text-sm">Save an admin key first.</p>;
  }
  if (err) {
    return <p className="text-red-300 text-sm">{err}</p>;
  }
  if (!data) {
    return <p className="text-lab-muted text-sm">Loading…</p>;
  }
  if (!data.ok) {
    return <p className="text-red-300 text-sm">Not found.</p>;
  }

  const hs = data.homeSummary as Record<string, unknown> | undefined;
  const steps = (data.steps as unknown[]) || [];
  const audit = (data.adminAudit as unknown[]) || [];
  const session = data.session as Record<string, unknown> | undefined;
  const userId = Number(session?.userId);
  const responsesForActions =
    (data.responsesForActions as Record<string, unknown>[]) || [];

  const env = data.workflowStateEnvelope as Record<string, unknown> | undefined;
  const ws = env?.workflowState as Record<string, unknown> | undefined;
  const dbStep =
    session?.currentStep != null ? String(session.currentStep) : "";
  const apiStep =
    ws?.currentStep != null ? String(ws.currentStep) : "";
  const dbOverall =
    session?.overallStatus != null ? String(session.overallStatus) : "";
  const apiOverall =
    ws?.overallStatus != null ? String(ws.overallStatus) : "";
  const instanceDrift =
    (dbStep !== apiStep || dbOverall !== apiOverall) &&
    Boolean(ws && Object.keys(ws).length > 0);

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center gap-3">
        <Link
          to="/mission-control/workflows"
          className="text-sm text-zinc-400 hover:underline"
        >
          ← Workflows
        </Link>
        <h2 className="text-base font-semibold font-mono">{workflowId}</h2>
      </div>

      {Number.isFinite(userId) ? (
        <McWorkflowOperatorPanel
          workflowId={workflowId!}
          userId={userId}
          homeSummary={hs || {}}
          responsesForActions={responsesForActions}
          onRefresh={loadDetail}
        />
      ) : (
        <p className="text-red-300 text-xs">
          Missing session userId; operator actions disabled.
        </p>
      )}

      <section>
        <h3 className="text-sm font-semibold text-lab-muted mb-2">Session</h3>
        <p className="text-xs text-lab-muted mb-2">
          DB row fields. Customer app uses the same engine read as{" "}
          <span className="font-mono text-zinc-300/90">workflowState</span> from{" "}
          <span className="font-mono text-zinc-300/90">GET …/state</span> (see
          envelope below).
        </p>
        {instanceDrift ? (
          <p className="text-xs text-amber-200/90 mb-2">
            Note:{" "}
            <span className="font-mono">currentStep</span> /{" "}
            <span className="font-mono">overallStatus</span> differ between this
            session row and the engine envelope below (often transient until
            repair runs).
          </p>
        ) : null}
        <pre className="text-xs overflow-auto max-h-48 rounded border border-white/10 bg-lab-surface p-3">
          {JSON.stringify(data.session, null, 2)}
        </pre>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-lab-muted mb-2">
          Event timeline
        </h3>
        <p className="text-xs text-lab-muted mb-2">
          Oldest first (append-only log). Not analytics — durable trace of workflow
          transitions and selected system outputs.
        </p>
        {eventsErr ? (
          <p className="text-amber-200/90 text-xs mb-2">{eventsErr}</p>
        ) : null}
        {events.length === 0 && !eventsErr ? (
          <p className="text-lab-muted text-xs">No events recorded yet.</p>
        ) : null}
        {events.length > 0 ? (
          <ul className="space-y-2 text-xs max-h-96 overflow-y-auto rounded border border-white/10 p-2">
            {events.map((e) => (
              <li
                key={e.id}
                className="rounded border border-white/5 bg-lab-surface/50 p-2"
              >
                <div className="text-lab-muted">
                  {e.createdAt ?? "—"} ·{" "}
                  <span className="font-mono text-zinc-300/90">{e.eventType}</span>
                </div>
                <div className="text-lab-muted mt-0.5">
                  actor: <span className="font-mono">{e.actor}</span> · source:{" "}
                  <span className="font-mono">{e.source}</span>
                  {e.stepId ? (
                    <>
                      {" "}
                      · step: <span className="font-mono">{e.stepId}</span>
                    </>
                  ) : null}
                </div>
                {e.metadata && Object.keys(e.metadata).length > 0 ? (
                  <pre className="mt-1 max-h-24 overflow-auto text-[10px] text-lab-muted">
                    {JSON.stringify(e.metadata, null, 2)}
                  </pre>
                ) : null}
                {e.previousState != null || e.newState != null ? (
                  <pre className="mt-1 max-h-32 overflow-auto text-[10px]">
                    {JSON.stringify(
                      { previous: e.previousState, new: e.newState },
                      null,
                      2,
                    )}
                  </pre>
                ) : null}
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      <section>
        <h3 className="text-sm font-semibold text-lab-muted mb-2">
          Home summary (authoritative hints)
        </h3>
        <div className="flex flex-wrap gap-2 mb-2">
          {hs?.overallStatus != null && (
            <McStatusChip>{String(hs.overallStatus)}</McStatusChip>
          )}
          {hs?.stalled ? (
            <McStatusChip tone="warn">stalled</McStatusChip>
          ) : null}
          {Boolean(hs?.adminOverridePresent) && (
            <McStatusChip tone="info">admin override</McStatusChip>
          )}
        </div>
        <pre className="text-xs overflow-auto max-h-96 rounded border border-white/10 bg-lab-surface p-3">
          {JSON.stringify(hs, null, 2)}
        </pre>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-lab-muted mb-2">Step rows</h3>
        <div className="overflow-x-auto rounded border border-white/10">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-white/10 bg-lab-surface text-lab-muted">
                <th className="p-2 text-left">step_id</th>
                <th className="p-2 text-left">status</th>
                <th className="p-2 text-left">attempts</th>
                <th className="p-2 text-left">async_state</th>
              </tr>
            </thead>
            <tbody>
              {steps.map((s: unknown) => {
                const row = s as Record<string, unknown>;
                return (
                  <tr key={String(row.step_id)} className="border-b border-white/5">
                    <td className="p-2 font-mono">{String(row.step_id)}</td>
                    <td className="p-2">{String(row.status)}</td>
                    <td className="p-2 tabular-nums">{String(row.attempt_count ?? "")}</td>
                    <td className="p-2 font-mono text-lab-muted max-w-xs truncate">
                      {row.async_task_state
                        ? JSON.stringify(row.async_task_state)
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-lab-muted mb-2">
          Full state envelope (same contract as customer{" "}
          <span className="font-mono">/state</span>)
        </h3>
        <pre className="text-xs overflow-auto max-h-64 rounded border border-white/10 bg-lab-surface p-3">
          {JSON.stringify(data.workflowStateEnvelope, null, 2)}
        </pre>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-lab-muted mb-2">
          Lifecycle / metadata
        </h3>
        <pre className="text-xs overflow-auto max-h-64 rounded border border-white/10 bg-lab-surface p-3">
          {JSON.stringify(data.metadata, null, 2)}
        </pre>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-lab-muted mb-2">
          Admin override history (session metadata)
        </h3>
        <pre className="text-xs overflow-auto max-h-48 rounded border border-white/10 bg-lab-surface p-3">
          {JSON.stringify(data.adminOverrideHistory, null, 2)}
        </pre>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-lab-muted mb-2">
          Admin audit (DB)
        </h3>
        <pre className="text-xs overflow-auto max-h-64 rounded border border-white/10 bg-lab-surface p-3">
          {JSON.stringify(audit, null, 2)}
        </pre>
      </section>

      <p className="text-xs text-lab-subtle">
        Engine file audit lines (reminder_delivery, step transitions) live in log
        aggregation, not PostgreSQL — tail application logs for workflow_audit JSON.
      </p>
    </div>
  );
}
