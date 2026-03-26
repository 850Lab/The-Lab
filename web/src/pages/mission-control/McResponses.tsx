import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { mccGet, getMissionControlAdminKey } from "@/lib/missionControlApi";
import { McStatusChip } from "@/components/mission-control/McStatusChip";
import { McResponseOverrideDialogs } from "@/components/mission-control/McResponseOverrideDialogs";
import type { ResponseOverrideOp } from "@/components/mission-control/McResponseOverrideDialogs";

type Row = Record<string, unknown> & { manualReviewSuggested?: boolean };

export function McResponses() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [reviewOnly, setReviewOnly] = useState(false);
  const [overrideOp, setOverrideOp] = useState<ResponseOverrideOp>(null);

  const load = useCallback(() => {
    if (!getMissionControlAdminKey()) return;
    const q = reviewOnly ? "?needs_review_only=true&limit=150" : "?limit=150";
    mccGet<{ items: Row[] }>(`/internal/admin/mission-control/responses${q}`)
      .then((r) => {
        setRows(r.items || []);
        setErr(null);
      })
      .catch((e) => setErr(String(e.message || e)));
  }, [reviewOnly]);

  useEffect(() => {
    load();
  }, [load]);

  if (!getMissionControlAdminKey()) {
    return <p className="text-lab-muted text-sm">Save an admin key first.</p>;
  }

  return (
    <div className="space-y-4">
      <McResponseOverrideDialogs
        op={overrideOp}
        onClose={() => setOverrideOp(null)}
        onSuccess={async () => {
          setOverrideOp(null);
          load();
        }}
      />
      <h2 className="text-base font-semibold">Responses</h2>
      <label className="flex items-center gap-2 text-sm text-lab-muted">
        <input
          type="checkbox"
          checked={reviewOnly}
          onChange={(e) => setReviewOnly(e.target.checked)}
        />
        Needs review / manual only (API filter)
      </label>
      <button
        type="button"
        onClick={load}
        className="rounded bg-lab-accent/90 px-3 py-1.5 text-sm text-white"
      >
        Reload
      </button>
      {err && <p className="text-red-300 text-sm">{err}</p>}
      <div className="overflow-x-auto rounded border border-white/10">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-white/10 bg-lab-surface text-lab-muted uppercase tracking-wide">
              <th className="p-2">Response</th>
              <th className="p-2">Workflow</th>
              <th className="p-2">Classification</th>
              <th className="p-2">Confidence</th>
              <th className="p-2">Next action</th>
              <th className="p-2">Review</th>
              <th className="p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r.response_id)} className="border-b border-white/5">
                <td className="p-2 font-mono">
                  {String(r.response_id).slice(0, 8)}…
                </td>
                <td className="p-2 font-mono">
                  <Link
                    to={`/mission-control/workflows/${String(r.workflow_id)}`}
                    className="text-sky-300 hover:underline"
                  >
                    {String(r.workflow_id).slice(0, 8)}…
                  </Link>
                </td>
                <td className="p-2 max-w-xs">
                  <div>{String(r.response_classification ?? r.classification_status ?? "—")}</div>
                  <div className="text-lab-subtle mt-1 line-clamp-2" title={String(r.classification_reasoning_safe ?? "")}>
                    {String(r.classification_reasoning_safe ?? "").slice(0, 160)}
                    {(r.classification_reasoning_safe as string)?.length > 160 ? "…" : ""}
                  </div>
                </td>
                <td className="p-2 tabular-nums">
                  {r.classification_confidence != null
                    ? String(r.classification_confidence)
                    : "—"}
                </td>
                <td className="p-2 text-lab-muted">
                  {String(r.recommended_next_action ?? "—")}
                </td>
                <td className="p-2">
                  {r.manualReviewSuggested ? (
                    <McStatusChip tone="warn">review</McStatusChip>
                  ) : (
                    <McStatusChip tone="neutral">—</McStatusChip>
                  )}
                </td>
                <td className="p-2 space-x-2 whitespace-nowrap">
                  <button
                    type="button"
                    className="text-sky-300 hover:underline"
                    onClick={() =>
                      setOverrideOp({ type: "classification", row: r })
                    }
                  >
                    Class
                  </button>
                  <button
                    type="button"
                    className="text-sky-300 hover:underline"
                    onClick={() =>
                      setOverrideOp({ type: "escalation", row: r })
                    }
                  >
                    Escalation
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && !err && (
          <p className="p-4 text-lab-muted text-sm">No responses.</p>
        )}
      </div>
    </div>
  );
}
