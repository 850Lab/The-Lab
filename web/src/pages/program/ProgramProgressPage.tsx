import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMeProgress } from "@/lib/orgProgramApi";
import {
  primaryProgramPath,
  PROGRAM_EYEBROW,
  programStageLabel,
} from "@/lib/orgProgramRoutes";
import type { ProgressResponse } from "@/lib/orgProgramTypes";
import { useAuth } from "@/providers/AuthContext";

export function ProgramProgressPage() {
  const { token } = useAuth();
  const [p, setP] = useState<ProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      setP(null);
      setErr(null);
      return;
    }
    setLoading(true);
    setErr(null);
    try {
      const j = await getMeProgress(token);
      setP(j);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load progress");
      setP(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <p className="text-sm text-lab-muted" role="status">
        Syncing where you are in the program…
      </p>
    );
  }

  if (err || !p) {
    return (
      <div className="rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
        <p className="font-medium text-red-100">We couldn&apos;t load your place in the program</p>
        <p className="mt-1 text-red-200/90">{err ?? "Not available"}</p>
        <p className="mt-2 text-sm text-red-200/75">
          You may need an active organization enrollment, or the service may be temporarily unavailable.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            to="/program"
            className="inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-zinc-950 hover:brightness-110"
          >
            Program hub
          </Link>
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex rounded-md border border-white/20 px-4 py-2 text-sm font-medium text-lab-text hover:bg-white/5"
          >
            Try again
          </button>
          <Link to="/" className="inline-flex items-center text-sm text-lab-muted hover:text-lab-text hover:underline">
            Home
          </Link>
        </div>
      </div>
    );
  }

  const paused = p.instructorState.paused || p.effectiveState.currentStep === "paused";
  const next = primaryProgramPath(p);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-muted">
            {PROGRAM_EYEBROW}
          </p>
          <h1 className="mt-1 text-xl font-semibold text-lab-text">Your place in the room</h1>
          <p className="mt-1 max-w-xl text-sm leading-relaxed text-lab-muted">
            The program is <span className="text-lab-text/90">working with you</span> — same path as
            your cohort, with your guide opening or holding the room so everyone stays together.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md border border-white/15 px-3 py-1.5 text-xs font-medium text-lab-text hover:bg-white/5"
        >
          Refresh
        </button>
      </div>

      {paused && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-50">
          <p className="font-medium text-amber-100">Your guide has paused the room</p>
          <p className="mt-1 text-amber-100/85">
            The whole cohort waits together — nothing is lost. When your organization releases the
            session, you&apos;ll pick up exactly here.
          </p>
          {p.instructorState.overrideReasonSafe && (
            <p className="mt-2 text-amber-100/75 italic">
              From your guide: {p.instructorState.overrideReasonSafe}
            </p>
          )}
        </div>
      )}

      <div className="rounded-lg border border-zinc-700/45 bg-white/[0.03] p-5">
        <h2 className="text-sm font-semibold text-lab-text">What you&apos;re in right now</h2>
        <p className="mt-1 text-xs text-lab-muted">
          This is the live chapter of your program — tailored to you, shared with your cohort.
        </p>
        <p className="mt-3 text-base font-medium text-lab-text">
          {programStageLabel(p.effectiveState.currentStep)}
          {p.effectiveState.nextStep ? (
            <span className="font-normal text-lab-muted">
              {" "}
              → then: {programStageLabel(p.effectiveState.nextStep)}
            </span>
          ) : null}
        </p>
        <p className="mt-2 text-xs text-lab-subtle">
          Already complete: {p.effectiveState.completedSteps.map(programStageLabel).join(" → ") || "—"}
        </p>
      </div>

      <details className="rounded-lg border border-white/[0.08] bg-lab-surface p-4 text-sm">
        <summary className="cursor-pointer text-xs font-medium text-lab-muted">
          More detail (optional)
        </summary>
        <div className="mt-4 grid gap-4 border-t border-white/[0.06] pt-4 sm:grid-cols-2">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-subtle">
              System record
            </p>
            <p className="mt-2 text-sm text-lab-text">
              {programStageLabel(p.systemState.currentStep)} → then:{" "}
              {p.systemState.nextStep ? programStageLabel(p.systemState.nextStep) : "—"}
            </p>
            <p className="mt-2 text-xs text-lab-subtle">
              Logged complete: {p.systemState.completedSteps.map(programStageLabel).join(", ") || "—"}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-subtle">
              What&apos;s open for you
            </p>
            <ul className="mt-2 space-y-1 text-xs text-lab-muted">
              <li>Share report: {p.gates.mayUploadReport ? "Open" : "Not yet"}</li>
              <li>Understand report: {p.gates.mayAnalyzeReport ? "Open" : "Not yet"}</li>
              <li>Choose focus: {p.gates.mayUseDisputeFlow ? "Open" : "Not yet"}</li>
              <li>Letters: {p.gates.mayGenerateLetters ? "Open" : "Not yet"}</li>
            </ul>
          </div>
        </div>
      </details>

      {!paused && (
        <Link
          to={next}
          className="inline-flex rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 hover:brightness-110"
        >
          Go to what&apos;s next
        </Link>
      )}
    </div>
  );
}
