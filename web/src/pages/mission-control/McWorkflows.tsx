import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { mccGet, getMissionControlAdminKey } from "@/lib/missionControlApi";
import { McStatusChip } from "@/components/mission-control/McStatusChip";

type Row = {
  workflowId: string;
  userId: number;
  currentStepId: string | null;
  overallStatus: string;
  waitingOn: string;
  stalled: boolean;
  escalationAvailable: boolean;
  nextBestAction: string;
  updatedAt: string | null;
};

type ListResp = {
  ok: boolean;
  items: Row[];
  returned: number;
  matchedBeforePagination: number;
  scannedSessions: number;
};

function fmt(d: string | null) {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleString();
  } catch {
    return d;
  }
}

export function McWorkflows() {
  const [rows, setRows] = useState<Row[]>([]);
  const [meta, setMeta] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [overallStatus, setOverallStatus] = useState("");
  const [currentStep, setCurrentStep] = useState("");
  const [waitingOn, setWaitingOn] = useState("");
  const [stalled, setStalled] = useState<string>("");
  const [hasFailed, setHasFailed] = useState<string>("");
  const [escalation, setEscalation] = useState<string>("");

  const load = () => {
    if (!getMissionControlAdminKey()) return;
    const q = new URLSearchParams();
    if (overallStatus) q.set("overall_status", overallStatus);
    if (currentStep) q.set("current_step", currentStep);
    if (waitingOn) q.set("waiting_on", waitingOn);
    if (stalled === "true") q.set("stalled", "true");
    if (stalled === "false") q.set("stalled", "false");
    if (hasFailed === "true") q.set("has_failed_step", "true");
    if (hasFailed === "false") q.set("has_failed_step", "false");
    if (escalation === "true") q.set("escalation_available", "true");
    if (escalation === "false") q.set("escalation_available", "false");
    q.set("limit", "75");
    const path = `/internal/admin/mission-control/workflows?${q.toString()}`;
    mccGet<ListResp>(path)
      .then((r) => {
        setRows(r.items || []);
        setMeta(
          `Showing ${r.returned} (matched ${r.matchedBeforePagination} after filters, scanned ${r.scannedSessions} sessions)`,
        );
        setErr(null);
      })
      .catch((e) => setErr(String(e.message || e)));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load on mount + apply
  }, []);

  if (!getMissionControlAdminKey()) {
    return <p className="text-lab-muted text-sm">Save an admin key first.</p>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold">Workflows</h2>
      <div className="flex flex-wrap gap-2 items-end text-sm">
        <label className="flex flex-col gap-0.5 text-xs text-lab-muted">
          Status
          <input
            value={overallStatus}
            onChange={(e) => setOverallStatus(e.target.value)}
            placeholder="active | failed | completed"
            className="rounded border border-white/15 bg-lab-elevated px-2 py-1 w-36 text-lab-text"
          />
        </label>
        <label className="flex flex-col gap-0.5 text-xs text-lab-muted">
          Current step
          <input
            value={currentStep}
            onChange={(e) => setCurrentStep(e.target.value)}
            placeholder="payment | mail | …"
            className="rounded border border-white/15 bg-lab-elevated px-2 py-1 w-32 text-lab-text"
          />
        </label>
        <label className="flex flex-col gap-0.5 text-xs text-lab-muted">
          Waiting on
          <input
            value={waitingOn}
            onChange={(e) => setWaitingOn(e.target.value)}
            placeholder="waiting_on_user"
            className="rounded border border-white/15 bg-lab-elevated px-2 py-1 w-40 text-lab-text"
          />
        </label>
        <label className="flex flex-col gap-0.5 text-xs text-lab-muted">
          Stalled
          <select
            value={stalled}
            onChange={(e) => setStalled(e.target.value)}
            className="rounded border border-white/15 bg-lab-elevated px-2 py-1 text-lab-text"
          >
            <option value="">any</option>
            <option value="true">yes</option>
            <option value="false">no</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-xs text-lab-muted">
          Failed step
          <select
            value={hasFailed}
            onChange={(e) => setHasFailed(e.target.value)}
            className="rounded border border-white/15 bg-lab-elevated px-2 py-1 text-lab-text"
          >
            <option value="">any</option>
            <option value="true">yes</option>
            <option value="false">no</option>
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-xs text-lab-muted">
          Escalation
          <select
            value={escalation}
            onChange={(e) => setEscalation(e.target.value)}
            className="rounded border border-white/15 bg-lab-elevated px-2 py-1 text-lab-text"
          >
            <option value="">any</option>
            <option value="true">available</option>
            <option value="false">not</option>
          </select>
        </label>
        <button
          type="button"
          onClick={load}
          className="rounded bg-lab-accent/90 px-3 py-1.5 text-sm font-medium text-white"
        >
          Apply
        </button>
      </div>
      {err && <p className="text-red-300 text-sm">{err}</p>}
      <p className="text-xs text-lab-muted">{meta}</p>
      <div className="overflow-x-auto rounded border border-white/10">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-lab-surface text-lab-muted uppercase tracking-wide">
              <th className="p-2 font-medium">Workflow</th>
              <th className="p-2 font-medium">User</th>
              <th className="p-2 font-medium">Step</th>
              <th className="p-2 font-medium">Status</th>
              <th className="p-2 font-medium">Waiting</th>
              <th className="p-2 font-medium">Stalled</th>
              <th className="p-2 font-medium">Esc.</th>
              <th className="p-2 font-medium">Updated</th>
              <th className="p-2 font-medium">Next action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.workflowId}
                className="border-b border-white/5 hover:bg-lab-elevated/40"
              >
                <td className="p-2 font-mono">
                  <Link
                    className="text-sky-300 hover:underline"
                    to={`/mission-control/workflows/${r.workflowId}`}
                  >
                    {r.workflowId.slice(0, 8)}…
                  </Link>
                </td>
                <td className="p-2 tabular-nums">{r.userId}</td>
                <td className="p-2 font-mono">{r.currentStepId ?? "—"}</td>
                <td className="p-2">
                  <McStatusChip
                    tone={
                      r.overallStatus === "failed"
                        ? "bad"
                        : r.overallStatus === "completed"
                          ? "ok"
                          : "neutral"
                    }
                  >
                    {r.overallStatus}
                  </McStatusChip>
                </td>
                <td className="p-2 text-lab-muted">{r.waitingOn}</td>
                <td className="p-2">
                  {r.stalled ? (
                    <McStatusChip tone="warn">yes</McStatusChip>
                  ) : (
                    <McStatusChip tone="neutral">no</McStatusChip>
                  )}
                </td>
                <td className="p-2">
                  {r.escalationAvailable ? (
                    <McStatusChip tone="info">yes</McStatusChip>
                  ) : (
                    <McStatusChip tone="neutral">no</McStatusChip>
                  )}
                </td>
                <td className="p-2 text-lab-muted whitespace-nowrap">
                  {fmt(r.updatedAt)}
                </td>
                <td className="p-2 text-lab-muted max-w-xs truncate" title={r.nextBestAction}>
                  {r.nextBestAction}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !err && (
          <p className="p-4 text-lab-muted text-sm">No rows.</p>
        )}
      </div>
    </div>
  );
}
