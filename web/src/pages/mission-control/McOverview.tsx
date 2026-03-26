import { useEffect, useState } from "react";
import { mccGet, getMissionControlAdminKey } from "@/lib/missionControlApi";

type Overview = {
  ok: boolean;
  counts: Record<string, number>;
  note?: string;
};

function Card({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border border-white/10 bg-lab-surface p-3 min-w-[140px]">
      <div className="text-[11px] uppercase tracking-wide text-lab-subtle">
        {label}
      </div>
      <div className="text-2xl font-semibold tabular-nums mt-1">{value}</div>
      {sub && <div className="text-xs text-lab-muted mt-1">{sub}</div>}
    </div>
  );
}

export function McOverview() {
  const [data, setData] = useState<Overview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!getMissionControlAdminKey()) {
      setData(null);
      setErr(null);
      return;
    }
    mccGet<Overview>("/internal/admin/mission-control/overview")
      .then(setData)
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  if (!getMissionControlAdminKey()) {
    return (
      <p className="text-lab-muted text-sm">Save an admin key to load overview.</p>
    );
  }
  if (err) {
    return <p className="text-red-300 text-sm">{err}</p>;
  }
  if (!data?.ok) {
    return <p className="text-lab-muted text-sm">Loading…</p>;
  }

  const c = data.counts;
  const num = (k: string) => c[k] ?? 0;

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold">Operational summary</h2>
      <p className="text-xs text-lab-muted max-w-3xl">{data.note}</p>
      <div className="flex flex-wrap gap-3">
        <Card label="Active workflows" value={num("workflows_active")} />
        <Card label="Failed (overall)" value={num("workflows_failed")} />
        <Card label="Completed" value={num("workflows_completed")} />
        <Card
          label="Stalled (sample)"
          value={num("stalled_in_active_sample")}
          sub={`of ${num("active_sample_size")} active`}
        />
        <Card
          label="Waiting on user (sample)"
          value={num("waiting_on_user_in_sample")}
        />
        <Card
          label="Waiting on system (sample)"
          value={num("waiting_on_system_in_sample")}
        />
        <Card
          label="Recovery suggested (sample)"
          value={num("recovery_actions_non_empty_in_sample")}
        />
        <Card label="Reminders failed" value={num("reminders_failed")} />
        <Card label="Reminders queued" value={num("reminders_queued")} />
        <Card label="Reminders eligible" value={num("reminders_eligible")} />
        <Card
          label="Responses need review"
          value={num("responses_needing_review")}
        />
        <Card
          label="Any failed step (distinct wf)"
          value={num("workflows_with_any_failed_step")}
        />
      </div>
    </div>
  );
}
