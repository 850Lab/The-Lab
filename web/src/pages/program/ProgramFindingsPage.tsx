import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMeFindings } from "@/lib/orgProgramApi";
import type { FindingsResponse } from "@/lib/orgProgramTypes";
import { PROGRAM_EYEBROW } from "@/lib/orgProgramRoutes";
import { useAuth } from "@/providers/AuthContext";

function SummaryRow({ label, value }: { label: string; value: unknown }) {
  const display =
    value == null
      ? "—"
      : typeof value === "string" || typeof value === "number"
        ? String(value)
        : "—";
  return (
    <div className="flex justify-between gap-2">
      <span className="text-lab-muted">{label}</span>
      <span className="text-lab-text">{display}</span>
    </div>
  );
}

export function ProgramFindingsPage() {
  const { token } = useAuth();
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setData(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setErr(null);
      try {
        const j = await getMeFindings(token);
        if (!cancelled) setData(j);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Could not load what we found");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  if (loading) {
    return (
      <p className="text-sm text-lab-muted" role="status">
        Pulling your report insights together…
      </p>
    );
  }

  if (err) {
    return (
      <div className="rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
        <p className="font-medium text-red-100">We couldn&apos;t load this view</p>
        <p className="mt-1 text-red-200/90">{err}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            to="/program/upload"
            className="inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-zinc-950 hover:brightness-110"
          >
            Share your report
          </Link>
          <Link to="/program" className="inline-flex items-center text-sm text-lab-accent hover:underline">
            Program hub
          </Link>
          <Link to="/" className="inline-flex items-center text-sm text-lab-muted hover:text-lab-text hover:underline">
            Home
          </Link>
        </div>
      </div>
    );
  }

  if (!data || data.processingStatus === "no_report") {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-6">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
          {PROGRAM_EYEBROW}
        </p>
        <h1 className="mt-2 text-xl font-semibold text-lab-text">Nothing to review yet</h1>
        <p className="mt-2 text-sm text-lab-muted">
          Share your bureau PDF first — we&apos;ll read it and bring the important pieces here.
        </p>
        <Link
          to="/program/upload"
          className="mt-4 inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-zinc-950"
        >
          Share your report
        </Link>
      </div>
    );
  }

  const summary = data.summary as Record<string, unknown> | null;
  const claims = data.reviewClaims ?? [];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
          {PROGRAM_EYEBROW}
        </p>
        <h1 className="mt-2 text-xl font-semibold text-lab-text">What we found for you</h1>
        <p className="mt-1 text-sm text-lab-muted">
          We&apos;ve read your report and surfaced what matters for your next move. When you&apos;re
          ready, you&apos;ll choose what to focus on — the program keeps everything organized.
        </p>
      </div>

      {summary && (
        <div className="grid gap-3 rounded-lg border border-white/10 bg-lab-surface p-4 text-sm sm:grid-cols-2">
          <SummaryRow label="Bureau" value={summary.bureau} />
          <SummaryRow label="Topics we surfaced" value={summary.reviewClaimsCount} />
          <SummaryRow label="Items worth a closer look" value={summary.violationsCount} />
        </div>
      )}

      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-lab-text">
          Your topics ({claims.length})
        </h2>
        <ul className="space-y-2">
          {claims.map((c, i) => {
            const id = String(c.review_claim_id ?? i);
            const summaryText = String(c.summary ?? c.question ?? "Item");
            const rtype = String(c.review_type ?? "");
            return (
              <li
                key={id}
                className="rounded-md border border-white/[0.08] bg-lab-elevated/60 px-3 py-2"
              >
                <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                  {rtype.replace(/_/g, " ")}
                </p>
                <p className="mt-1 text-sm text-lab-text">{summaryText}</p>
              </li>
            );
          })}
        </ul>
      </div>

      <Link
        to="/program/select"
        className="inline-flex rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 hover:brightness-110"
      >
        Choose what to focus on
      </Link>
    </div>
  );
}
