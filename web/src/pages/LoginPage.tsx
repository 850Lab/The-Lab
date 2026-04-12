import { motion } from "framer-motion";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { DemoContinuationStrip } from "@/components/DemoContinuationStrip";
import { ProgramPathContinuationStrip } from "@/components/ProgramPathContinuationStrip";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import {
  DEMO_PROGRAM_ENTRY_DEFAULT_NEXT,
  shouldShowDemoContinuationStrip,
} from "@/lib/demoProgramBridge";
import {
  isProgramOnboardingNext,
  resolvedProgramNextFromSearch,
} from "@/lib/programEntryContinuation";
import { postAuthTargetFromSearchAndState, safeAppPath } from "@/lib/postAuthRedirect";
import { LaunchHubNavLink } from "@/components/LaunchHubNavLink";
import { useAuth } from "@/providers/AuthContext";

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const programEyebrow =
    shouldShowDemoContinuationStrip(location.search) ||
    isProgramOnboardingNext(resolvedProgramNextFromSearch(location.search));
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const from = (location.state as { from?: string } | null)?.from;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const u = await signIn(email.trim(), password);
      if (!u.emailVerified) {
        try {
          sessionStorage.setItem("850lab_verify_send_initial", "1");
        } catch {
          /* ignore */
        }
        const q = new URLSearchParams(location.search);
        let returnTo = safeAppPath(q.get("next"));
        if (!returnTo && q.get("from") === "demo") {
          returnTo = DEMO_PROGRAM_ENTRY_DEFAULT_NEXT;
        }
        navigate("/verify-email", {
          replace: true,
          state: {
            sendInitialCode: true,
            ...(returnTo ? { returnTo } : {}),
          },
        });
        return;
      }
      navigate(
        postAuthTargetFromSearchAndState(location.search, from, "/login"),
        { replace: true },
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <TopBarMinimal />
      <main className="relative z-10 mx-auto max-w-md px-4 pb-16 pt-24 sm:px-6 sm:pt-28">
        <p className="step-eyebrow-left">850 Lab · Sign in</p>
        <motion.h1
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-2 text-2xl font-semibold text-lab-text"
        >
          Sign in
        </motion.h1>
        <p className="mt-2 text-sm leading-relaxed text-lab-muted">
          {programEyebrow ? (
            <>
              Same email and password as your 850 Lab account — you&apos;re signing back into the
              same guided flow, not a separate login screen.
            </>
          ) : (
            <>Use the same email and password as your 850 Lab account.</>
          )}
        </p>
        <DemoContinuationStrip stage="login" />
        <ProgramPathContinuationStrip stage="login" />

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          {error ? (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200/95">
              {error}
            </p>
          ) : null}
          <div>
            <label htmlFor="login-email" className="sr-only">
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              required
              className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
            />
          </div>
          <div>
            <label htmlFor="login-password" className="sr-only">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              required
              className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
            />
            <div className="mt-2 text-right">
              <Link
                to={`/forgot-password${location.search}`}
                className="text-sm font-medium text-lab-accent hover:text-zinc-100"
              >
                Forgot password?
              </Link>
            </div>
          </div>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-lab-muted">
          No account?{" "}
          <Link
            to={`/signup${location.search}`}
            className="font-medium text-lab-accent hover:text-zinc-100"
          >
            Create one
          </Link>
        </p>
        <LaunchHubNavLink />
      </main>
    </div>
  );
}
