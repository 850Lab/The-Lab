import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  mccGet,
  getMissionControlAdminKey,
  adminDeliverReminderMc,
  adminQueueReminderMc,
  adminSkipReminder,
} from "@/lib/missionControlApi";
import { McStatusChip } from "@/components/mission-control/McStatusChip";
import { McActionModal } from "@/components/mission-control/McActionModal";

type Row = Record<string, unknown>;

type RemOp = null | { kind: "skip" | "queue" | "deliver"; id: string };

function tone(s: string): "neutral" | "ok" | "warn" | "bad" | "info" {
  if (s === "failed") return "bad";
  if (s === "sent") return "ok";
  if (s === "queued") return "info";
  return "neutral";
}

export function McReminders() {
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("eligible,queued,sent,failed");
  const [remOp, setRemOp] = useState<RemOp>(null);

  const load = useCallback(() => {
    if (!getMissionControlAdminKey()) return;
    const q = statusFilter.trim()
      ? `?status=${encodeURIComponent(statusFilter)}&limit=250`
      : "?limit=250";
    mccGet<{ items: Row[] }>(`/internal/admin/mission-control/reminders${q}`)
      .then((r) => {
        setRows(r.items || []);
        setErr(null);
      })
      .catch((e) => setErr(String(e.message || e)));
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  if (!getMissionControlAdminKey()) {
    return <p className="text-lab-muted text-sm">Save an admin key first.</p>;
  }

  return (
    <div className="space-y-4">
      <McActionModal
        open={remOp?.kind === "skip"}
        title="Skip reminder"
        requireAuditFields
        onClose={() => setRemOp(null)}
        onRun={async (op) => {
          await adminSkipReminder(remOp!.id, op!);
          setRemOp(null);
          load();
        }}
      />
      <McActionModal
        open={remOp?.kind === "queue"}
        title="Queue reminder for delivery"
        confirmLabel="Queue"
        requireAuditFields={false}
        onClose={() => setRemOp(null)}
        onRun={async () => {
          await adminQueueReminderMc(remOp!.id);
          setRemOp(null);
          load();
        }}
      />
      <McActionModal
        open={remOp?.kind === "deliver"}
        title="Deliver queued reminder now"
        confirmLabel="Deliver"
        requireAuditFields={false}
        onClose={() => setRemOp(null)}
        onRun={async () => {
          await adminDeliverReminderMc(remOp!.id);
          setRemOp(null);
          load();
        }}
      >
        <p className="text-xs text-amber-200/90">
          Invokes live delivery for a queued reminder.
        </p>
      </McActionModal>
      <h2 className="text-base font-semibold">Reminders</h2>
      <div className="flex flex-wrap gap-2 items-center text-sm">
        <label className="text-lab-muted text-xs">
          Status (comma-separated)
          <input
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="ml-2 rounded border border-white/15 bg-lab-elevated px-2 py-1 w-64 text-lab-text"
          />
        </label>
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
              <th className="p-2">Reminder</th>
              <th className="p-2">Workflow</th>
              <th className="p-2">Type</th>
              <th className="p-2">Status</th>
              <th className="p-2">Channel</th>
              <th className="p-2">Created</th>
              <th className="p-2">Sent</th>
              <th className="p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const st = String(r.status ?? "");
              return (
                <tr key={String(r.reminder_id)} className="border-b border-white/5">
                  <td className="p-2 font-mono">
                    {String(r.reminder_id).slice(0, 8)}…
                  </td>
                  <td className="p-2 font-mono">
                    <Link
                      to={`/mission-control/workflows/${String(r.workflow_id)}`}
                      className="text-sky-300 hover:underline"
                    >
                      {String(r.workflow_id).slice(0, 8)}…
                    </Link>
                  </td>
                  <td className="p-2">{String(r.reminder_type)}</td>
                  <td className="p-2">
                    <McStatusChip tone={tone(st)}>{st}</McStatusChip>
                  </td>
                  <td className="p-2 text-lab-muted">
                    {String(r.delivery_channel ?? "—")}
                  </td>
                  <td className="p-2 text-lab-muted whitespace-nowrap">
                    {r.created_at ? String(r.created_at) : "—"}
                  </td>
                  <td className="p-2 text-lab-muted whitespace-nowrap">
                    {r.sent_at ? String(r.sent_at) : "—"}
                  </td>
                  <td className="p-2 space-x-2 whitespace-nowrap">
                    {st !== "sent" ? (
                      <button
                        type="button"
                        className="text-sky-300 hover:underline"
                        onClick={() =>
                          setRemOp({
                            kind: "skip",
                            id: String(r.reminder_id),
                          })
                        }
                      >
                        Skip
                      </button>
                    ) : null}
                    {st === "eligible" ? (
                      <button
                        type="button"
                        className="text-sky-300 hover:underline"
                        onClick={() =>
                          setRemOp({
                            kind: "queue",
                            id: String(r.reminder_id),
                          })
                        }
                      >
                        Queue
                      </button>
                    ) : null}
                    {st === "queued" ? (
                      <button
                        type="button"
                        className="text-sky-300 hover:underline"
                        onClick={() =>
                          setRemOp({
                            kind: "deliver",
                            id: String(r.reminder_id),
                          })
                        }
                      >
                        Deliver
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {rows.length === 0 && !err && (
          <p className="p-4 text-lab-muted text-sm">No reminders.</p>
        )}
      </div>
    </div>
  );
}
