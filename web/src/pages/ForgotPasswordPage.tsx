import { motion } from "framer-motion";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { LaunchHubNavLink } from "@/components/LaunchHubNavLink";
import { authForgotPassword, authResetPassword } from "@/lib/authApi";

function signupStylePasswordErrors(password: string): string | null {
  if (password.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Z]/.test(password))
    return "Password must include at least one uppercase letter.";
  if (!/[a-z]/.test(password))
    return "Password must include at least one lowercase letter.";
  if (!/\d/.test(password)) return "Password must include at least one number.";
  return null;
}

export function ForgotPasswordPage() {
  const location = useLocation();
  const search = location.search || "";
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sentNote, setSentNote] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const handleRequestCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSentNote(null);
    setBusy(true);
    try {
      await authForgotPassword(email.trim());
      setSentNote(
        "If an account exists for that email, we sent a reset code. Check your inbox (and spam).",
      );
      setStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    setError(null);
    setSentNote(null);
    setBusy(true);
    try {
      await authForgotPassword(email.trim());
      setSentNote("If an account exists for that email, we sent another code.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const pwErr = signupStylePasswordErrors(password);
    if (pwErr) {
      setError(pwErr);
      return;
    }
    if (password !== password2) {
      setError("Passwords don’t match.");
      return;
    }
    setBusy(true);
    try {
      await authResetPassword(email.trim(), code.trim(), password);
      setDone(true);
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
        <motion.h1
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-2xl font-semibold text-lab-text"
        >
          Reset password
        </motion.h1>
        <p className="mt-2 text-sm leading-relaxed text-lab-muted">
          {step === "email"
            ? "Enter the email for your 850 Lab account. We’ll send a short code if we find it."
            : "Enter the code from your email and choose a new password."}
        </p>

        {done ? (
          <div className="mt-8 space-y-4">
            <p className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100/95">
              Your password was updated. You can sign in with the new password.
            </p>
            <Link
              to={`/login${search}`}
              className="block w-full rounded-lg bg-lab-accent py-2.5 text-center text-sm font-semibold text-white"
            >
              Back to sign in
            </Link>
          </div>
        ) : step === "email" ? (
          <form onSubmit={handleRequestCode} className="mt-8 space-y-4">
            {error ? (
              <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200/95">
                {error}
              </p>
            ) : null}
            <div>
              <label htmlFor="forgot-email" className="sr-only">
                Email
              </label>
              <input
                id="forgot-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                required
                className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
              />
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            >
              {busy ? "Sending…" : "Send reset code"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleReset} className="mt-8 space-y-4">
            {error ? (
              <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200/95">
                {error}
              </p>
            ) : null}
            {sentNote ? (
              <p className="rounded-lg border border-white/[0.08] bg-lab-elevated/50 px-3 py-2 text-sm text-lab-muted">
                {sentNote}
              </p>
            ) : null}
            <p className="text-xs text-lab-subtle">
              Resetting for <span className="text-lab-text">{email}</span>
              {" · "}
              <button
                type="button"
                className="font-medium text-lab-accent hover:text-sky-300"
                onClick={() => {
                  setStep("email");
                  setSentNote(null);
                  setError(null);
                  setCode("");
                  setPassword("");
                  setPassword2("");
                }}
              >
                Use a different email
              </button>
            </p>
            <div>
              <label htmlFor="forgot-code" className="sr-only">
                Reset code
              </label>
              <input
                id="forgot-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="Code from email"
                required
                className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
              />
            </div>
            <div>
              <label htmlFor="forgot-password" className="sr-only">
                New password
              </label>
              <input
                id="forgot-password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="New password"
                required
                className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
              />
            </div>
            <div>
              <label htmlFor="forgot-password2" className="sr-only">
                Confirm new password
              </label>
              <input
                id="forgot-password2"
                type="password"
                autoComplete="new-password"
                value={password2}
                onChange={(e) => setPassword2(e.target.value)}
                placeholder="Confirm new password"
                required
                className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle"
              />
            </div>
            <p className="text-xs text-lab-subtle">
              Use at least 8 characters with upper and lowercase letters and a number.
            </p>
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            >
              {busy ? "Updating…" : "Set new password"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void handleResend()}
              className="w-full rounded-lg border border-white/[0.12] py-2.5 text-sm font-medium text-lab-text hover:bg-white/[0.04] disabled:opacity-60"
            >
              Resend code
            </button>
          </form>
        )}

        {!done ? (
          <p className="mt-6 text-center text-sm text-lab-muted">
            <Link
              to={`/login${search}`}
              className="font-medium text-lab-accent hover:text-sky-300"
            >
              Back to sign in
            </Link>
          </p>
        ) : null}
        <LaunchHubNavLink />
      </main>
    </div>
  );
}
