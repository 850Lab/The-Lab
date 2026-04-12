import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getGtmPageBySlug, type GtmConnection } from "@/lib/launchPreviewManifest";
import { runVerification, type ProbeState } from "@/lib/launchPreviewProbes";

function badge(s: ProbeState["status"]) {
  switch (s) {
    case "pass":
      return <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-xs text-emerald-100">Connected</span>;
    case "fail":
      return <span className="rounded bg-red-500/20 px-2 py-0.5 text-xs text-red-100">Not reachable</span>;
    case "skipped":
      return <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-100">Needs session</span>;
    case "checking":
      return <span className="rounded bg-white/10 px-2 py-0.5 text-xs text-lab-muted">Checking…</span>;
    default:
      return <span className="rounded bg-white/10 px-2 py-0.5 text-xs text-lab-muted">—</span>;
  }
}

function detailText(state: ProbeState): string {
  if (state.status === "idle") return "Pending";
  if (state.status === "checking") return "…";
  return state.detail;
}

export function LaunchPreviewInspector() {
  const { slug } = useParams<{ slug: string }>();
  const page = slug ? getGtmPageBySlug(slug) : undefined;

  const [results, setResults] = useState<Record<string, ProbeState>>({});

  const connections = page?.connections ?? [];

  useEffect(() => {
    if (!page) return;
    const initial: Record<string, ProbeState> = {};
    for (const c of page.connections) {
      initial[c.id] = { status: "checking" };
    }
    setResults(initial);

    let cancelled = false;
    void (async () => {
      // Run probes in parallel — serial was N× round-trip latency.
      await Promise.all(
        page.connections.map(async (conn) => {
          const r = await runVerification(conn.verification);
          if (!cancelled) {
            setResults((prev) => ({ ...prev, [conn.id]: r }));
          }
        }),
      );
    })();

    return () => {
      cancelled = true;
    };
  }, [page]);

  const iframeSrc = useMemo(() => {
    if (!page?.path || page.status === "planned") return null;
    if (typeof window === "undefined") return null;
    return `${window.location.origin}${page.path}`;
  }, [page]);

  if (!page) {
    return (
      <main className="mx-auto max-w-3xl px-4 py-12">
        <p className="text-lab-muted">Unknown page.</p>
        <Link to="/launch-preview" className="mt-4 inline-block text-lab-accent hover:underline">
          ← Dashboard
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Link
          to="/launch-preview"
          className="text-sm text-violet-300 hover:text-violet-100 hover:underline"
        >
          ← All pages
        </Link>
        <span className="text-lab-subtle">/</span>
        <h1 className="text-lg font-semibold text-lab-text">{page.label}</h1>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            page.status === "done"
              ? "bg-emerald-500/20 text-emerald-100"
              : page.status === "processing"
                ? "bg-amber-500/25 text-amber-100"
                : "bg-white/10 text-lab-muted"
          }`}
        >
          {page.status === "done" ? "Done" : page.status === "processing" ? "Processing" : "Coming soon"}
        </span>
      </div>
      <p className="mb-6 max-w-3xl text-sm text-lab-muted">{page.description}</p>

      {page.status === "planned" && (
        <div className="mb-8 rounded-2xl border border-white/10 bg-lab-surface p-10 text-center">
          <p className="text-sm font-medium text-lab-text">Not built yet</p>
          <p className="mt-2 text-sm text-lab-muted">
            This surface is on the roadmap. There is no route to embed yet.
            {page.plannedTarget && (
              <>
                {" "}
                <span className="text-lab-subtle">({page.plannedTarget})</span>
              </>
            )}
          </p>
        </div>
      )}

      {page.status === "processing" && (
        <div className="mb-6 rounded-xl border border-amber-500/30 bg-amber-950/25 p-4">
          <p className="text-sm font-medium text-amber-50">Build in progress</p>
          {page.activeWork && (
            <>
              <p className="mt-2 text-sm text-amber-100/85">{page.activeWork.summary}</p>
              <ul className="mt-3 space-y-1 font-mono text-xs text-amber-200/80">
                {page.activeWork.paths.map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </>
          )}
          <p className="mt-3 text-xs text-amber-200/70">
            Preview below uses the closest live route: <code className="text-amber-100">{page.path ?? "—"}</code>
          </p>
        </div>
      )}

      {iframeSrc && (page.status === "done" || page.status === "processing") && (
        <div className="mb-8 overflow-hidden rounded-2xl border border-white/15 bg-black/40 shadow-xl">
          <div className="flex flex-col gap-1 border-b border-white/10 bg-lab-surface px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <span className="font-mono text-xs text-lab-muted">Live page (same app, full interaction)</span>
              <p className="mt-0.5 text-[11px] text-lab-subtle">
                Expect a short delay: the iframe boots a second copy of the SPA (React, auth, workflow).
                Use “Open in new tab” for the fastest path when you only need the page.
              </p>
            </div>
            <a
              href={iframeSrc}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-zinc-400 hover:underline"
            >
              Open in new tab
            </a>
          </div>
          <iframe
            title={page.label}
            src={iframeSrc}
            className="h-[min(78vh,900px)] w-full bg-lab-bg"
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox"
          />
        </div>
      )}

      <section className="rounded-2xl border border-white/10 bg-lab-surface/60 p-5">
        <h2 className="text-base font-semibold text-lab-text">Connections</h2>
        <p className="mt-1 text-xs text-lab-muted">
          Declared = wired in repo (treated as linked). API = live HTTP check to your workflow API (
          <code className="text-violet-200">workflowApiBase()</code>
          ). 401 with no session still counts as reachable for auth-gated routes.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-white/10 text-xs uppercase text-lab-subtle">
                <th className="pb-2 pr-4 font-medium">Integration</th>
                <th className="pb-2 pr-4 font-medium">Description</th>
                <th className="pb-2 pr-4 font-medium">Status</th>
                <th className="pb-2 font-medium">Detail</th>
              </tr>
            </thead>
            <tbody>
              {connections.map((row: GtmConnection) => {
                const st = results[row.id] ?? { status: "idle" as const };
                return (
                  <tr key={row.id} className="border-b border-white/[0.06] align-top">
                    <td className="py-3 pr-4 font-medium text-lab-text">{row.name}</td>
                    <td className="py-3 pr-4 text-lab-muted">{row.description}</td>
                    <td className="py-3 pr-4 whitespace-nowrap">{badge(st.status)}</td>
                    <td className="py-3 text-xs text-lab-subtle">{detailText(st)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
