import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  formatMccErrorMessage,
  getMissionControlAdminKey,
  mccConvertDemoLeadToOrg,
  mccFetchDemoLeads,
  type MissionControlDemoLeadRow,
} from "@/lib/missionControlApi";

function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

async function copyText(text: string): Promise<boolean> {
  const t = text.trim();
  if (!t) return false;
  try {
    await navigator.clipboard.writeText(t);
    return true;
  } catch {
    return false;
  }
}

export function McDemoLeads() {
  const [rows, setRows] = useState<MissionControlDemoLeadRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [scenarioFilter, setScenarioFilter] = useState<string>("");
  const [copied, setCopied] = useState<string | null>(null);
  const [convertFor, setConvertFor] = useState<MissionControlDemoLeadRow | null>(null);
  const [convertName, setConvertName] = useState("");
  const [convertBusy, setConvertBusy] = useState(false);
  const [convertErr, setConvertErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!getMissionControlAdminKey()) return;
    setLoading(true);
    setErr(null);
    try {
      const data = await mccFetchDemoLeads(200);
      setRows(data);
    } catch (e) {
      setErr(formatMccErrorMessage(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!copied) return;
    const t = window.setTimeout(() => setCopied(null), 2000);
    return () => window.clearTimeout(t);
  }, [copied]);

  const scenarioOptions = useMemo(() => {
    const s = new Set<string>();
    for (const r of rows) {
      if (r.scenario_id) s.add(r.scenario_id);
    }
    return Array.from(s).sort();
  }, [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((r) => {
      if (scenarioFilter && (r.scenario_id || "") !== scenarioFilter) {
        return false;
      }
      if (!q) return true;
      const intentStr =
        r.meta && typeof r.meta === "object" && "intent" in r.meta
          ? String((r.meta as { intent?: unknown }).intent ?? "")
          : "";
      const blob = [
        r.name,
        r.email,
        r.phone || "",
        r.scenario_id || "",
        r.workflow_id || "",
        r.source,
        intentStr,
      ]
        .join(" ")
        .toLowerCase();
      return blob.includes(q);
    });
  }, [rows, query, scenarioFilter]);

  if (!getMissionControlAdminKey()) {
    return <p className="text-lab-muted text-sm">Save an admin key first.</p>;
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-lab-text">Demo leads</h2>
        <p className="mt-1 max-w-xl text-sm text-lab-muted">
          Contacts from the try-first home (lead form after the live sample). Legacy{" "}
          <Link to={{ pathname: "/", hash: "live-demo" }} className="text-zinc-400 hover:underline">
            /demo
          </Link>{" "}
          redirects to the same page. Newest first. Convert a lead to create an organization and link
          this row for continuity.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[200px] flex-1">
          <label htmlFor="demo-lead-search" className="text-xs text-lab-muted">
            Search name, email, or phone
          </label>
          <input
            id="demo-lead-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type to filter…"
            className="mt-1 w-full rounded border border-white/15 bg-lab-elevated px-2 py-1.5 text-sm text-lab-text placeholder:text-lab-subtle focus:border-lab-accent/50 focus:outline-none"
          />
        </div>
        {scenarioOptions.length > 0 ? (
          <div>
            <label htmlFor="demo-lead-scenario" className="text-xs text-lab-muted">
              Scenario
            </label>
            <select
              id="demo-lead-scenario"
              value={scenarioFilter}
              onChange={(e) => setScenarioFilter(e.target.value)}
              className="mt-1 block rounded border border-white/15 bg-lab-elevated px-2 py-1.5 text-sm text-lab-text focus:border-lab-accent/50 focus:outline-none"
            >
              <option value="">All</option>
              {scenarioOptions.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </div>
        ) : null}
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded bg-lab-accent/90 px-3 py-1.5 text-sm font-medium text-white hover:bg-lab-accent disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      <p className="text-sm text-lab-muted">
        Showing <span className="font-medium text-lab-text">{filtered.length}</span>
        {filtered.length !== rows.length ? (
          <>
            {" "}
            of <span className="font-medium text-lab-text">{rows.length}</span>
          </>
        ) : null}{" "}
        lead{filtered.length === 1 ? "" : "s"}
      </p>

      {err ? <p className="text-sm text-red-300">{err}</p> : null}

      {!loading && !err && rows.length === 0 ? (
        <div className="rounded border border-white/10 bg-lab-surface/50 px-4 py-8 text-center text-sm text-lab-muted">
          No demo leads yet. Submissions from the home lead form will appear here.
        </div>
      ) : null}

      {filtered.length === 0 && rows.length > 0 ? (
        <p className="text-sm text-lab-muted">No leads match your search.</p>
      ) : null}

      {filtered.length > 0 ? (
        <div className="overflow-x-auto rounded border border-white/10">
          <table className="w-full min-w-[800px] text-left text-xs">
            <thead>
              <tr className="border-b border-white/10 bg-lab-surface text-lab-muted uppercase tracking-wide">
                <th className="p-2">Submitted</th>
                <th className="p-2">Name</th>
                <th className="p-2">Email</th>
                <th className="p-2">Phone</th>
                <th className="p-2">Intent</th>
                <th className="p-2">Scenario</th>
                <th className="p-2">Workflow</th>
                <th className="p-2">Source</th>
                <th className="p-2">Org</th>
                <th className="p-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id} className="border-b border-white/5 align-top">
                  <td className="whitespace-nowrap p-2 text-lab-muted">
                    {formatWhen(r.created_at)}
                  </td>
                  <td className="p-2 font-medium text-lab-text">{r.name}</td>
                  <td className="p-2">
                    <a
                      href={`mailto:${r.email}`}
                      className="break-all text-zinc-400 hover:underline"
                    >
                      {r.email}
                    </a>
                  </td>
                  <td className="p-2">
                    {r.phone ? (
                      <a href={`tel:${r.phone.replace(/\s/g, "")}`} className="text-zinc-400 hover:underline">
                        {r.phone}
                      </a>
                    ) : (
                      <span className="text-lab-subtle">—</span>
                    )}
                  </td>
                  <td className="p-2 text-lab-muted">
                    {r.meta &&
                    typeof r.meta === "object" &&
                    "intent" in r.meta &&
                    String((r.meta as { intent?: unknown }).intent || "").trim()
                      ? String((r.meta as { intent: string }).intent)
                      : "—"}
                  </td>
                  <td className="p-2 font-mono text-lab-muted">
                    {r.scenario_id || "—"}
                  </td>
                  <td className="p-2 font-mono text-lab-muted">
                    {r.workflow_id ? (
                      <Link
                        to={`/mission-control/workflows/${r.workflow_id}`}
                        className="text-zinc-400 hover:underline"
                        title={r.workflow_id}
                      >
                        {r.workflow_id.slice(0, 8)}…
                      </Link>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-2 text-lab-muted">{r.source}</td>
                  <td className="p-2 font-mono text-lab-muted">
                    {r.converted_organization_id != null ? (
                      <span title="Linked organization id">{r.converted_organization_id}</span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-2">
                    <div className="flex flex-wrap gap-1">
                      {r.converted_organization_id == null ? (
                        <button
                          type="button"
                          onClick={() => {
                            setConvertErr(null);
                            setConvertFor(r);
                            setConvertName(r.name?.trim() || "New organization");
                          }}
                          className="rounded border border-emerald-500/40 px-2 py-0.5 text-emerald-200/90 hover:bg-emerald-500/10"
                        >
                          Convert to org
                        </button>
                      ) : null}
                      <button
                        type="button"
                        onClick={async () => {
                          const ok = await copyText(r.email);
                          if (ok) setCopied(`email:${r.id}`);
                        }}
                        className="rounded border border-white/15 px-2 py-0.5 text-lab-muted hover:bg-white/5 hover:text-lab-text"
                      >
                        {copied === `email:${r.id}` ? "Copied" : "Copy email"}
                      </button>
                      {r.phone ? (
                        <button
                          type="button"
                          onClick={async () => {
                            const ok = await copyText(r.phone!);
                            if (ok) setCopied(`phone:${r.id}`);
                          }}
                          className="rounded border border-white/15 px-2 py-0.5 text-lab-muted hover:bg-white/5 hover:text-lab-text"
                        >
                          {copied === `phone:${r.id}` ? "Copied" : "Copy phone"}
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {convertFor ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="convert-org-title"
        >
          <div className="w-full max-w-md rounded-lg border border-white/15 bg-lab-surface p-5 shadow-xl">
            <h3 id="convert-org-title" className="text-base font-semibold text-lab-text">
              Create organization from lead
            </h3>
            <p className="mt-2 text-sm text-lab-muted">
              Lead #{convertFor.id} — {convertFor.email}. This creates a new org row and links the
              lead. Add members and enrollments separately.
            </p>
            <label htmlFor="convert-org-name" className="mt-4 block text-xs text-lab-muted">
              Organization name
            </label>
            <input
              id="convert-org-name"
              type="text"
              value={convertName}
              onChange={(e) => setConvertName(e.target.value)}
              className="mt-1 w-full rounded border border-white/15 bg-lab-elevated px-3 py-2 text-sm text-lab-text"
            />
            {convertErr ? (
              <p className="mt-2 text-sm text-red-300">{convertErr}</p>
            ) : null}
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setConvertFor(null);
                  setConvertErr(null);
                }}
                className="rounded border border-white/15 px-3 py-1.5 text-sm text-lab-muted hover:bg-white/5"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={convertBusy || !convertName.trim()}
                onClick={async () => {
                  setConvertBusy(true);
                  setConvertErr(null);
                  try {
                    await mccConvertDemoLeadToOrg(convertFor.id, convertName.trim());
                    setConvertFor(null);
                    await load();
                  } catch (e) {
                    setConvertErr(formatMccErrorMessage(e));
                  } finally {
                    setConvertBusy(false);
                  }
                }}
                className="rounded bg-lab-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-lab-accent/90 disabled:opacity-50"
              >
                {convertBusy ? "Creating…" : "Create org"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
