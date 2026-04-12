import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  formatMccErrorMessage,
  getMissionControlAdminKey,
  mccApplyArchitectScenario,
  mccFetchArchitectScenarios,
  type ArchitectScenarioRow,
} from "@/lib/missionControlApi";
import { useAuth } from "@/providers/AuthContext";

export function McArchitectAccessPage() {
  const navigate = useNavigate();
  const { adoptTrustedSession } = useAuth();
  const [scenarios, setScenarios] = useState<ArchitectScenarioRow[]>([]);
  const [loadingList, setLoadingList] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [resetConsumer, setResetConsumer] = useState(true);

  const hasKey = getMissionControlAdminKey().length > 0;

  const load = useCallback(async () => {
    if (!hasKey) return;
    setLoadingList(true);
    setErr(null);
    try {
      const rows = await mccFetchArchitectScenarios();
      setScenarios(rows);
    } catch (e) {
      setErr(formatMccErrorMessage(e));
    } finally {
      setLoadingList(false);
    }
  }, [hasKey]);

  useEffect(() => {
    void load();
  }, [load]);

  const onApply = async (scenarioId: string) => {
    if (!hasKey) return;
    setBusyId(scenarioId);
    setErr(null);
    try {
      const res = await mccApplyArchitectScenario({
        scenarioId,
        resetConsumerWorkflow: resetConsumer,
      });
      if (!res.sessionToken || !res.launchPath) {
        throw new Error("Invalid apply response");
      }
      await adoptTrustedSession(res.sessionToken);
      navigate(res.launchPath);
    } catch (e) {
      setErr(formatMccErrorMessage(e));
    } finally {
      setBusyId(null);
    }
  };

  if (!hasKey) {
    return (
      <div className="max-w-xl space-y-3 text-sm text-lab-muted">
        <h2 className="text-base font-semibold text-lab-text">Architect access</h2>
        <p>
          Save the workflow admin API key in the Mission Control header first — same secret as{" "}
          <code className="text-lab-text">WORKFLOW_ADMIN_API_SECRET</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-base font-semibold text-lab-text">Architect access</h2>
        <p className="mt-1 text-sm text-lab-muted leading-relaxed">
          Seed <span className="text-lab-text/90">real</span> workflows and org relationships, then
          receive a normal session for the fixture user. Requires admin key; not available to public
          visitors.
        </p>
        <label className="mt-3 flex cursor-pointer items-center gap-2 text-sm text-lab-muted">
          <input
            type="checkbox"
            checked={resetConsumer}
            onChange={(e) => setResetConsumer(e.target.checked)}
            className="rounded border-white/20 bg-lab-elevated"
          />
          Reset consumer dispute workflow before seeding (recommended)
        </label>
      </div>

      {err && (
        <div
          className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100"
          role="alert"
        >
          {err}
        </div>
      )}

      {loadingList && (
        <p className="text-sm text-lab-muted" role="status">
          Loading scenarios…
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border border-white/10">
        <table className="min-w-full text-left text-sm">
          <thead className="border-b border-white/10 bg-lab-surface text-xs uppercase tracking-wide text-lab-subtle">
            <tr>
              <th className="px-3 py-2 font-medium">Scenario</th>
              <th className="px-3 py-2 font-medium">Persona</th>
              <th className="px-3 py-2 font-medium">Fixture</th>
              <th className="px-3 py-2 font-medium">Launch</th>
              <th className="px-3 py-2 font-medium"> </th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr key={s.id} className="border-b border-white/[0.06] last:border-0">
                <td className="px-3 py-2 align-top text-lab-text">
                  <div className="font-medium">{s.label}</div>
                  <div className="mt-0.5 text-xs text-lab-muted">{s.description}</div>
                  <div className="mt-1 font-mono text-[10px] text-lab-subtle">{s.id}</div>
                </td>
                <td className="px-3 py-2 align-top text-lab-muted">{s.persona}</td>
                <td className="px-3 py-2 align-top font-mono text-[10px] leading-snug text-lab-subtle">
                  {s.fixtureHint ?? "—"}
                </td>
                <td className="px-3 py-2 align-top font-mono text-xs text-lab-accent">{s.launchPath}</td>
                <td className="px-3 py-2 align-top">
                  <button
                    type="button"
                    disabled={busyId != null}
                    onClick={() => void onApply(s.id)}
                    className="rounded-md bg-lab-accent px-3 py-1.5 text-xs font-semibold text-zinc-950 hover:brightness-110 disabled:opacity-40"
                  >
                    {busyId === s.id ? "Applying…" : "Apply & open"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-lab-subtle">
        Fixture emails use the <code className="text-lab-muted">850lab-architect.invalid</code>{" "}
        domain.{" "}
        <Link to="/mission-control" className="text-lab-accent hover:underline">
          Back to overview
        </Link>
      </p>
    </div>
  );
}
