import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { mccGet, getMissionControlAdminKey } from "@/lib/missionControlApi";

type Item = {
  workflowId: string;
  userId: number;
  reasons: string[];
  currentStepId: string | null;
  overallStatus: string;
  waitingOn: string;
  stalled: boolean;
  nextBestAction: string;
};

export function McExceptions() {
  const [items, setItems] = useState<Item[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!getMissionControlAdminKey()) return;
    mccGet<{ ok: boolean; items: Item[] }>(
      "/internal/admin/mission-control/exceptions?limit=150",
    )
      .then((r) => {
        setItems(r.items || []);
        setErr(null);
      })
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  if (!getMissionControlAdminKey()) {
    return <p className="text-lab-muted text-sm">Save an admin key first.</p>;
  }
  if (err) {
    return <p className="text-red-300 text-sm">{err}</p>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold">Exceptions queue</h2>
      <p className="text-xs text-lab-muted max-w-3xl">
        Workflows with failed steps, failed overall status, stalled signals, recovery
        actions, mail partial failure metadata, unclear latest classification, escalation
        available, or failed reminder delivery.
      </p>
      <div className="overflow-x-auto rounded border border-white/10">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-white/10 bg-lab-surface text-lab-muted uppercase tracking-wide">
              <th className="p-2">Workflow</th>
              <th className="p-2">User</th>
              <th className="p-2">Reasons</th>
              <th className="p-2">Step</th>
              <th className="p-2">Status</th>
              <th className="p-2">Next action</th>
              <th className="p-2">Mission Control</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.workflowId} className="border-b border-white/5">
                <td className="p-2 font-mono">
                  <Link
                    className="text-sky-300 hover:underline"
                    to={`/mission-control/workflows/${r.workflowId}`}
                  >
                    {r.workflowId.slice(0, 8)}…
                  </Link>
                </td>
                <td className="p-2">{r.userId}</td>
                <td className="p-2 text-lab-muted max-w-md">
                  {r.reasons.join(", ")}
                </td>
                <td className="p-2 font-mono">{r.currentStepId ?? "—"}</td>
                <td className="p-2">{r.overallStatus}</td>
                <td className="p-2 text-lab-muted max-w-xs truncate" title={r.nextBestAction}>
                  {r.nextBestAction}
                </td>
                <td className="p-2">
                  <Link
                    className="text-sky-300 hover:underline text-xs"
                    to={`/mission-control/workflows/${r.workflowId}#operator-actions`}
                  >
                    Open actions
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && (
          <p className="p-4 text-lab-muted text-sm">No exception rows.</p>
        )}
      </div>
    </div>
  );
}
