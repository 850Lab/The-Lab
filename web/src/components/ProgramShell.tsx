import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { getMeOrgProgram } from "@/lib/orgProgramApi";
import type { OrgProgramResponse } from "@/lib/orgProgramTypes";
import {
  NAV_GUIDE_DESK,
  NAV_ORG_OVERVIEW,
  NAV_SETUP,
  PROGRAM_EYEBROW,
  PROGRAM_NAV,
} from "@/lib/orgProgramRoutes";
import { useAuth } from "@/providers/AuthContext";

export function ProgramShell() {
  const loc = useLocation();
  const { token } = useAuth();
  const [orgCtx, setOrgCtx] = useState<OrgProgramResponse | null>(null);
  const [orgCtxReady, setOrgCtxReady] = useState(false);

  useEffect(() => {
    if (!token) {
      setOrgCtx(null);
      setOrgCtxReady(false);
      return;
    }
    setOrgCtxReady(false);
    let cancelled = false;
    void (async () => {
      try {
        const o = await getMeOrgProgram(token);
        if (!cancelled) setOrgCtx(o);
      } catch {
        if (!cancelled) setOrgCtx(null);
      } finally {
        if (!cancelled) setOrgCtxReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const role = orgCtx?.membership?.role ?? "";
  const showInstructor = role === "org_instructor";
  const showBuyer = role === "org_admin";
  const showSetup = showInstructor || showBuyer;

  if (!token) {
    return (
      <div className="min-h-full bg-lab-bg">
        <TopBarMinimal />
        <main className="mx-auto max-w-lg px-4 pb-16 pt-24 sm:px-6 sm:pt-28">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
            {PROGRAM_EYEBROW}
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-lab-text">
            Sign in to open your program
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-lab-muted">
            Host-led cohorts live here — shared progress and one rhythm with your guide. Use the
            account your organization invited, or continue with the main 850 Lab path if you&apos;re
            working on your own.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Link
              to="/login"
              className="inline-flex justify-center rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-sky-400"
            >
              Sign in
            </Link>
            <Link
              to="/signup"
              className="inline-flex justify-center rounded-md border border-white/15 bg-lab-surface px-5 py-2.5 text-sm font-medium text-lab-text hover:bg-white/5"
            >
              Create account
            </Link>
          </div>
          <p className="mt-8 text-sm text-lab-muted">
            <Link
              to={{ pathname: "/", hash: "live-demo" }}
              className="font-medium text-lab-accent hover:underline"
            >
              Try the live demo
            </Link>
            <span className="mx-2 text-lab-subtle">·</span>
            <Link to="/" className="font-medium text-lab-accent hover:underline">
              Consumer program home
            </Link>
          </p>
        </main>
      </div>
    );
  }

  if (!orgCtxReady) {
    return (
      <div className="min-h-full bg-lab-bg">
        <TopBarMinimal />
        <main className="mx-auto max-w-3xl px-4 pb-16 pt-28 sm:px-6 sm:pt-32">
          <p className="text-sm text-lab-muted" role="status">
            Loading your program…
          </p>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-lab-bg">
      <TopBarMinimal />
      <nav
        className="fixed left-0 right-0 top-14 z-30 border-b border-white/[0.06] bg-lab-surface/90 backdrop-blur-sm"
        aria-label="Program sections"
      >
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-1 px-4 py-2 sm:px-6">
          {PROGRAM_NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/program"}
              className={({ isActive }) =>
                [
                  "rounded-md px-2.5 py-1.5 text-xs font-medium sm:text-sm",
                  isActive
                    ? "bg-lab-accent/20 text-lab-text"
                    : "text-lab-muted hover:bg-white/5 hover:text-lab-text",
                ].join(" ")
              }
            >
              {label}
            </NavLink>
          ))}
          {showSetup && (
            <NavLink
              to="/program/setup"
              className={({ isActive }) =>
                [
                  "rounded-md px-2.5 py-1.5 text-xs font-medium sm:text-sm",
                  isActive
                    ? "bg-violet-500/25 text-lab-text"
                    : "text-lab-muted hover:bg-white/5 hover:text-lab-text",
                ].join(" ")
              }
            >
              {NAV_SETUP}
            </NavLink>
          )}
          {showInstructor && (
            <NavLink
              to="/program/instructor"
              className={({ isActive }) =>
                [
                  "rounded-md px-2.5 py-1.5 text-xs font-medium sm:text-sm",
                  isActive
                    ? "bg-violet-500/25 text-lab-text"
                    : "text-lab-muted hover:bg-white/5 hover:text-lab-text",
                ].join(" ")
              }
            >
              {NAV_GUIDE_DESK}
            </NavLink>
          )}
          {showBuyer && (
            <NavLink
              to="/program/org-insights"
              className={({ isActive }) =>
                [
                  "rounded-md px-2.5 py-1.5 text-xs font-medium sm:text-sm",
                  isActive
                    ? "bg-violet-500/25 text-lab-text"
                    : "text-lab-muted hover:bg-white/5 hover:text-lab-text",
                ].join(" ")
              }
            >
              {NAV_ORG_OVERVIEW}
            </NavLink>
          )}
        </div>
      </nav>
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-28 sm:px-6 sm:pt-32">
        <Outlet key={loc.pathname} />
      </main>
    </div>
  );
}
