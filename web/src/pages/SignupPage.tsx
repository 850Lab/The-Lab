import { motion } from "framer-motion";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { LaunchHubNavLink } from "@/components/LaunchHubNavLink";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { DemoContinuationStrip } from "@/components/DemoContinuationStrip";
import { ProgramPathContinuationStrip } from "@/components/ProgramPathContinuationStrip";
import {
  DEMO_PROGRAM_ENTRY_DEFAULT_NEXT,
  shouldShowDemoContinuationStrip,
} from "@/lib/demoProgramBridge";
import {
  isProgramOnboardingNext,
  resolvedProgramNextFromSearch,
} from "@/lib/programEntryContinuation";
import { safeAppPath } from "@/lib/postAuthRedirect";
import { useAuth } from "@/providers/AuthContext";

export function SignupPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const programEyebrow =
    shouldShowDemoContinuationStrip(location.search) ||
    isProgramOnboardingNext(resolvedProgramNextFromSearch(location.search));
  const { signUp } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== password2) {
      setError("Passwords don’t match.");
      return;
    }
    setBusy(true);
    try {
      await signUp(email.trim(), password, displayName.trim());
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
        <p className="step-eyebrow-left">850 Lab · Create account</p>
        <motion.h1
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-2 text-2xl font-semibold text-lab-text"
        >
          Create account
        </motion.h1>
        <p className="mt-2 text-sm leading-relaxed text-lab-muted">
          {programEyebrow ? (
            <>
              One account for your whole guided round — same path before and after you sign in. Next
              we confirm your email so we can continue securely.
            </>
          ) : (
            <>
              Create an account to save your progress in 850 Lab. You&apos;ll verify your email next.
            </>
          )}
        </p>
        <DemoContinuationStrip stage="signup" />
        <ProgramPathContinuationStrip stage="signup" />

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          {error ? (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200/95">
              {error}
            </p>
          ) : null}
          <input
            type="text"
            autoComplete="name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Your name"
            required
            className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
          />
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            required
            className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
          />
          <input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (8+ chars, upper, lower, number)"
            required
            minLength={8}
            className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
          />
          <input
            type="password"
            autoComplete="new-password"
            value={password2}
            onChange={(e) => setPassword2(e.target.value)}
            placeholder="Confirm password"
            required
            className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
          />
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-lab-muted">
          Already have an account?{" "}
          <Link
            to={`/login${location.search}`}
            className="font-medium text-lab-accent hover:text-zinc-100"
          >
            Sign in
          </Link>
        </p>
        <LaunchHubNavLink />
      </main>
    </div>
  );
}
