import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  MCC_ADMIN_KEY_CHANGE_EVENT,
  getMissionControlAdminKey,
  mccGet,
} from "@/lib/missionControlApi";

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
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = () => {
      const key = getMissionControlAdminKey();
      if (!key) {
        setData(null);
        setErr(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setErr(null);
      void mccGet<Overview>("/internal/admin/mission-control/overview")
        .then(setData)
        .catch((e) => setErr(String((e as Error).message || e)))
        .finally(() => setLoading(false));
    };
    load();
    window.addEventListener(MCC_ADMIN_KEY_CHANGE_EVENT, load);
    return () => window.removeEventListener(MCC_ADMIN_KEY_CHANGE_EVENT, load);
  }, []);

  const keyPresent = getMissionControlAdminKey().length > 0;

  if (!keyPresent) {
    return (
      <div className="max-w-2xl space-y-4">
        <h2 className="text-base font-semibold text-lab-text">Operational summary</h2>
        <p className="text-sm text-lab-muted leading-relaxed">
          Paste the workflow admin API key in the header (same value as{" "}
          <code className="rounded bg-lab-elevated px-1 py-0.5 text-xs text-lab-text">
            WORKFLOW_ADMIN_API_SECRET
          </code>{" "}
          on the server), then click <span className="text-lab-text">Save</span>. Counts load from
          the live API — no page refresh needed.
        </p>
        <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-50">
          <p className="font-medium text-amber-100">What to do next</p>
          <p className="mt-1 text-amber-100/85">
            Use <span className="text-amber-50">Admin key</span> above → Save → this board fills in.
            Then open workflows or exceptions for drill-down.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Link
            to="/mission-control/workflows"
            className="rounded-md border border-white/15 px-3 py-1.5 text-lab-muted hover:border-white/25 hover:text-lab-text"
          >
            Workflows (needs key)
          </Link>
          <Link
            to="/mission-control/exceptions"
            className="rounded-md border border-white/15 px-3 py-1.5 text-lab-muted hover:border-white/25 hover:text-lab-text"
          >
            Exceptions
          </Link>
        </div>
      </div>
    );
  }

  if (loading && !data?.ok) {
    return (
      <div className="space-y-4">
        <h2 className="text-base font-semibold text-lab-text">Operational summary</h2>
        <p className="text-sm text-lab-muted" role="status">
          Loading live counts…
        </p>
      </div>
    );
  }

  if (err) {
    return (
      <div className="max-w-2xl space-y-4">
        <h2 className="text-base font-semibold text-lab-text">Operational summary</h2>
        <div
          className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100"
          role="alert"
        >
          <p className="font-medium">Could not load overview</p>
          <p className="mt-1 text-red-100/90">{err}</p>
          <p className="mt-2 text-xs text-red-200/75">
            Check the admin key, CORS or proxy (<code className="text-red-100">VITE_WORKFLOW_API_URL</code>
            ), and that the workflow API is up.
          </p>
        </div>
        <div className="flex flex-wrap gap-3 text-sm">
          <button
            type="button"
            className="rounded-md bg-lab-accent px-4 py-2 font-medium text-zinc-950 hover:brightness-110"
            onClick={() => window.dispatchEvent(new CustomEvent(MCC_ADMIN_KEY_CHANGE_EVENT))}
          >
            Retry
          </button>
          <Link to="/mission-control/workflows" className="text-lab-accent hover:underline">
            Workflows
          </Link>
          <Link to="/mission-control/reminders" className="text-lab-accent hover:underline">
            Reminders
          </Link>
        </div>
      </div>
    );
  }

  if (!data?.ok) {
    return (
      <div className="space-y-4">
        <h2 className="text-base font-semibold text-lab-text">Operational summary</h2>
        <p className="text-sm text-lab-muted" role="status">
          No summary payload yet…
        </p>
      </div>
    );
  }

  const c = data.counts;
  const num = (k: string) => c[k] ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-lab-text">Operational summary</h2>
          {data.note && (
            <p className="text-xs text-lab-muted max-w-3xl mt-1">{data.note}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <Link
            to="/mission-control/workflows"
            className="rounded-md border border-white/15 px-2.5 py-1.5 text-lab-accent hover:bg-white/5"
          >
            Workflows
          </Link>
          <Link
            to="/mission-control/exceptions"
            className="rounded-md border border-white/15 px-2.5 py-1.5 text-lab-accent hover:bg-white/5"
          >
            Exceptions
          </Link>
          <Link
            to="/mission-control/responses"
            className="rounded-md border border-white/15 px-2.5 py-1.5 text-lab-accent hover:bg-white/5"
          >
            Responses
          </Link>
          <Link
            to="/mission-control/reminders"
            className="rounded-md border border-white/15 px-2.5 py-1.5 text-lab-accent hover:bg-white/5"
          >
            Reminders
          </Link>
        </div>
      </div>
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
