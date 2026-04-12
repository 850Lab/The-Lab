import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getMeOrgProgram, getMeProgress } from "@/lib/orgProgramApi";
import {
  primaryProgramPath,
  PROGRAM_EYEBROW,
  programStageLabel,
} from "@/lib/orgProgramRoutes";
import type {
  OrgProgramResponse,
  ProgressResponse,
} from "@/lib/orgProgramTypes";
import { PROGRAM_STAGE_ORDER } from "@/lib/orgProgramTypes";
import { useAuth } from "@/providers/AuthContext";

function stepLabel(step: string): string {
  const m: Record<string, string> = {
    enrollment: "Enrolled",
    upload: "Upload report",
    findings_ready: "Findings ready",
    selections_saved: "Disputes selected",
    letters_generated: "Letters generated",
    paused: "Room held by guide",
  };
  return m[step] ?? step;
}

export function ProgramHomePage() {
  const { token } = useAuth();
  const [org, setOrg] = useState<OrgProgramResponse | null>(null);
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setOrg(null);
      setProgress(null);
      setErr(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setErr(null);
      try {
        const o = await getMeOrgProgram(token);
        if (!cancelled) setOrg(o);
        if (o.enrollment) {
          try {
            const p = await getMeProgress(token);
            if (!cancelled) setProgress(p);
          } catch {
            if (!cancelled) setProgress(null);
          }
        } else if (!cancelled) {
          setProgress(null);
        }
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "Could not load program");
        }
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
      <p className="text-center text-sm text-lab-muted" role="status">
        Gathering your place in the program…
      </p>
    );
  }

  if (err) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
        <p className="font-medium">We couldn&apos;t load your program just now</p>
        <p className="mt-1 text-red-200/80">{err}</p>
        <Link to="/" className="mt-3 inline-block text-lab-accent hover:underline">
          Return home
        </Link>
      </div>
    );
  }

  if (!org?.enrollment) {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-6">
        <h1 className="text-lg font-semibold text-lab-text">No program seat on this account</h1>
        <p className="mt-2 text-sm text-lab-muted">
          This login isn&apos;t enrolled in a cohort yet. If you expected an invite, reach out to your
          organization — we&apos;ll get you seated.
        </p>
        <Link
          to="/"
          className="mt-6 inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-medium text-zinc-950 hover:brightness-110"
        >
          Return home
        </Link>
      </div>
    );
  }

  const paused =
    progress?.instructorState?.paused || progress?.effectiveState?.currentStep === "paused";
  const accessLocked = Boolean(progress?.programAccess && !progress.programAccess.allowed);
  const next = accessLocked
    ? "/program"
    : progress
      ? primaryProgramPath(progress)
      : "/program/upload";
  const currentStep =
    progress?.effectiveState?.currentStep ?? progress?.currentStep ?? "enrollment";
  const completed = new Set(progress?.completedSteps ?? []);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-lab-muted">
          {PROGRAM_EYEBROW}
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-lab-text">
          {org.organization?.name ?? "Your program"}
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-lab-muted">
          You&apos;re part of a <span className="text-lab-text/90">single shared journey</span> with
          your cohort. The program keeps everyone aligned; your guide can pause or reopen the room
          so no one is left behind.
        </p>
        <p className="mt-2 text-sm text-lab-muted">
          Your seat: <span className="text-lab-text">{org.enrollment.status}</span>
        </p>
      </div>

      {accessLocked && (
        <div
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-50"
          role="status"
        >
          <p className="font-medium text-amber-100">Your organization is finishing activation</p>
          <p className="mt-1 text-amber-100/85">
            We&apos;re holding new work gently until your host completes program billing — so you
            never invest effort that can&apos;t move forward. You can still see where you stand;
            everything opens when they activate.
          </p>
        </div>
      )}

      {progress && (
        <div className="rounded-lg border border-white/10 bg-lab-surface p-5">
          <h2 className="text-sm font-semibold text-lab-text">How this program moves</h2>
          <p className="mt-1 text-xs leading-relaxed text-lab-muted">
            Same story, same timing as your cohort — not a solo to-do list. After letters, your guide
            may bring you together live or send the next chapter; staying here keeps you in sync with
            the room.
          </p>
          <ol className="mt-4 space-y-2">
            {PROGRAM_STAGE_ORDER.map((step, i) => {
              const done = completed.has(step);
              const active = !paused && currentStep === step;
              return (
                <li
                  key={step}
                  className={[
                    "flex gap-3 rounded-md border px-3 py-2 text-sm",
                    done
                      ? "border-emerald-500/25 bg-emerald-500/5 text-emerald-100"
                      : active
                        ? "border-zinc-500/40 bg-zinc-500/[0.1] text-lab-text"
                        : "border-white/[0.06] text-lab-muted",
                  ].join(" ")}
                >
                  <span className="font-mono text-xs text-lab-muted">{i + 1}</span>
                  <span>{stepLabel(step)}</span>
                  {done && (
                    <span className="ml-auto text-xs text-emerald-200/80">Done</span>
                  )}
                  {active && (
                    <span className="ml-auto text-xs text-zinc-300/90">You are here with the cohort</span>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      )}

      {paused && (
        <div
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-50"
          role="status"
        >
          <p className="font-medium text-amber-100">Your guide has the room on hold</p>
          <p className="mt-1 text-amber-100/85">
            Everyone pauses together — that&apos;s intentional. You can still look back at what
            you&apos;ve done; when your guide releases the room, the program picks up right where it
            left off.
          </p>
        </div>
      )}

      {progress && (
        <div className="rounded-lg border border-white/10 bg-lab-surface p-5">
          <h2 className="text-sm font-semibold text-lab-text">Where you are now</h2>
          <p className="mt-1 text-xs text-lab-muted">
            The program remembers everything you&apos;ve finished — you&apos;re never starting over.
          </p>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-lab-muted">Right now</dt>
              <dd className="text-right text-lab-text">
                {programStageLabel(progress.effectiveState?.currentStep ?? progress.currentStep)}
              </dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-lab-muted">Up next</dt>
              <dd className="text-right text-lab-text">
                {progress.effectiveState?.nextStep
                  ? programStageLabel(progress.effectiveState.nextStep)
                  : progress.nextStep
                    ? programStageLabel(progress.nextStep)
                    : "—"}
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-lab-subtle">
            Already behind you:{" "}
            {(progress.completedSteps ?? [])
              .map((s) => programStageLabel(s))
              .join(" → ") || "—"}
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Link
          to={next}
          className="inline-flex justify-center rounded-md bg-lab-accent px-5 py-2.5 text-center text-sm font-semibold text-zinc-950 hover:brightness-110"
        >
          {paused
            ? "See your status"
            : accessLocked
              ? "Program on hold"
              : "Continue your program"}
        </Link>
        <Link
          to="/program/progress"
          className="inline-flex justify-center rounded-md border border-white/15 px-5 py-2.5 text-center text-sm font-medium text-lab-text hover:bg-white/5"
        >
          Deeper look at your path
        </Link>
      </div>
    </div>
  );
}
