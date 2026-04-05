import { useMemo } from "react";
import { Link } from "react-router-dom";
import {
  GTM_PREVIEW_PAGES,
  countByStatus,
  type GtmPageStatus,
  type GtmPreviewPage,
} from "@/lib/launchPreviewManifest";

function statusStyles(status: GtmPageStatus): { bar: string; badge: string; label: string } {
  switch (status) {
    case "done":
      return {
        bar: "border-emerald-500/40 bg-emerald-950/25",
        badge: "bg-emerald-500/20 text-emerald-100",
        label: "Done",
      };
    case "processing":
      return {
        bar: "border-amber-500/50 bg-amber-950/30",
        badge: "bg-amber-500/25 text-amber-100",
        label: "Processing",
      };
    case "planned":
      return {
        bar: "border-white/10 bg-white/[0.03]",
        badge: "bg-white/10 text-lab-muted",
        label: "Coming soon",
      };
    default:
      return {
        bar: "border-white/10",
        badge: "bg-white/10 text-lab-muted",
        label: status,
      };
  }
}

function PageCard({ page }: { page: GtmPreviewPage }) {
  const st = statusStyles(page.status);
  return (
    <Link
      to={`/launch-preview/view/${page.slug}`}
      className={`group block rounded-2xl border p-5 transition hover:ring-1 hover:ring-violet-500/30 ${st.bar}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${st.badge}`}>{st.label}</span>
            {page.audience && (
              <span className="text-xs text-lab-subtle">{page.audience}</span>
            )}
          </div>
          <h3 className="mt-2 text-base font-semibold text-lab-text group-hover:text-violet-100">
            {page.label}
          </h3>
          <p className="mt-1 line-clamp-2 text-sm text-lab-muted">{page.description}</p>
          {page.path && (
            <p className="mt-2 font-mono text-xs text-lab-subtle">{page.path}</p>
          )}
          {page.status === "processing" && page.activeWork && (
            <div className="mt-3 rounded-lg border border-amber-500/20 bg-black/20 p-2 text-xs text-amber-100/90">
              <p className="font-medium text-amber-50">In progress</p>
              <p className="mt-1 text-amber-100/75">{page.activeWork.summary}</p>
              <ul className="mt-2 space-y-0.5 font-mono text-[10px] text-amber-200/70">
                {page.activeWork.paths.slice(0, 4).map((p) => (
                  <li key={p}>{p}</li>
                ))}
              </ul>
            </div>
          )}
          {page.status === "planned" && page.plannedTarget && (
            <p className="mt-2 text-xs uppercase tracking-wide text-lab-subtle">{page.plannedTarget}</p>
          )}
        </div>
        <span className="shrink-0 text-violet-300/80 opacity-0 transition group-hover:opacity-100">→</span>
      </div>
    </Link>
  );
}

export function LaunchPreviewDashboard() {
  const tallies = useMemo(() => countByStatus(), []);
  const sorted = useMemo(
    () =>
      [...GTM_PREVIEW_PAGES].sort((a, b) => {
        const order: GtmPageStatus[] = ["done", "processing", "planned"];
        const d = order.indexOf(a.status) - order.indexOf(b.status);
        if (d !== 0) return d;
        return a.label.localeCompare(b.label);
      }),
    [],
  );

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <div className="mb-8 flex flex-wrap gap-4 rounded-xl border border-white/10 bg-lab-surface/50 p-4">
        <div>
          <p className="text-xs text-lab-muted">Done</p>
          <p className="text-2xl font-semibold text-emerald-200">{tallies.done}</p>
        </div>
        <div>
          <p className="text-xs text-lab-muted">Processing</p>
          <p className="text-2xl font-semibold text-amber-200">{tallies.processing}</p>
        </div>
        <div>
          <p className="text-xs text-lab-muted">Coming soon</p>
          <p className="text-2xl font-semibold text-lab-muted">{tallies.planned}</p>
        </div>
        <p className="ml-auto max-w-md text-xs text-lab-muted self-center">
          Click any card: full interactive page (iframe) and live connection checks below. Declared items show as
          linked in codebase; API pings hit your workflow API base.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {sorted.map((page) => (
          <PageCard key={page.slug} page={page} />
        ))}
      </div>

      <section className="mt-12 rounded-xl border border-dashed border-white/15 bg-black/20 p-5 text-sm text-lab-muted">
        <p className="font-medium text-lab-text">Remove this hub later</p>
        <p className="mt-1">
          Delete <code className="text-violet-200">web/src/pages/launch-preview/</code>,{" "}
          <code className="text-violet-200">launchPreview*.ts</code>, and the{" "}
          <code className="text-violet-200">/launch-preview</code> routes in{" "}
          <code className="text-violet-200">App.tsx</code>.
        </p>
      </section>
    </main>
  );
}
