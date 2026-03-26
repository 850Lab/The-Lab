import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { mccGet, getMissionControlAdminKey } from "@/lib/missionControlApi";

type Row = Record<string, unknown>;

export function McAudit() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [wf, setWf] = useState("");

  const load = () => {
    if (!getMissionControlAdminKey()) return;
    const q = wf.trim()
      ? `?workflow_id=${encodeURIComponent(wf.trim())}&limit=250`
      : "?limit=250";
    mccGet<{ items: Row[] }>(`/internal/admin/mission-control/audit${q}`)
      .then((r) => {
        setRows(r.items || []);
        setErr(null);
      })
      .catch((e) => setErr(String(e.message || e)));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!getMissionControlAdminKey()) {
    return <p className="text-lab-muted text-sm">Save an admin key first.</p>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold">Admin audit</h2>
      <div className="flex flex-wrap gap-2 items-center text-sm">
        <input
          value={wf}
          onChange={(e) => setWf(e.target.value)}
          placeholder="Filter by workflow UUID (optional)"
          className="rounded border border-white/15 bg-lab-elevated px-2 py-1 w-80 font-mono text-xs text-lab-text"
        />
        <button
          type="button"
          onClick={load}
          className="rounded bg-lab-accent/90 px-3 py-1.5 text-sm text-white"
        >
          Reload
        </button>
      </div>
      {err && <p className="text-red-300 text-sm">{err}</p>}
      <div className="overflow-x-auto rounded border border-white/10">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-white/10 bg-lab-surface text-lab-muted uppercase tracking-wide">
              <th className="p-2">When</th>
              <th className="p-2">Workflow</th>
              <th className="p-2">Action</th>
              <th className="p-2">Actor</th>
              <th className="p-2">Reason</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r.audit_id)} className="border-b border-white/5">
                <td className="p-2 text-lab-muted whitespace-nowrap">
                  {String(r.created_at ?? "—")}
                </td>
                <td className="p-2 font-mono">
                  {r.workflow_id ? (
                    <Link
                      to={`/mission-control/workflows/${String(r.workflow_id)}`}
                      className="text-sky-300 hover:underline"
                    >
                      {String(r.workflow_id).slice(0, 8)}…
                    </Link>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="p-2 font-mono">{String(r.action_type)}</td>
                <td className="p-2 text-lab-muted">{String(r.actor_source)}</td>
                <td className="p-2 text-lab-muted max-w-md truncate" title={String(r.reason_safe ?? "")}>
                  {String(r.reason_safe ?? "").slice(0, 120)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !err && (
          <p className="p-4 text-lab-muted text-sm">No audit rows.</p>
        )}
      </div>
    </div>
  );
}
