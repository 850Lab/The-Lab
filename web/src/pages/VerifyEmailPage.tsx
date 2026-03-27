import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { safeAppPath } from "@/lib/postAuthRedirect";
import { useAuth } from "@/providers/AuthContext";

type VerifyLocationState = {
  sendInitialCode?: boolean;
  returnTo?: string;
};

export function VerifyEmailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { verifyEmail, resendVerification, user } = useAuth();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendBusy, setResendBusy] = useState(false);
  const [resendNote, setResendNote] = useState<string | null>(null);
  const initialSendRef = useRef(false);

  const locState = (location.state as VerifyLocationState | null) ?? null;
  const sendInitialCode = Boolean(locState?.sendInitialCode);
  const afterVerifyPath = safeAppPath(locState?.returnTo) ?? "/";

  useEffect(() => {
    if (!sendInitialCode || initialSendRef.current) return;
    initialSendRef.current = true;
    void (async () => {
      try {
        await resendVerification();
        setResendNote("We sent a code to your email.");
      } catch {
        setResendNote("Could not send email yet. Use Resend code below.");
      }
    })();
  }, [sendInitialCode, resendVerification]);

  useEffect(() => {
    if (user?.emailVerified) {
      navigate(afterVerifyPath, { replace: true });
    }
  }, [user?.emailVerified, navigate, afterVerifyPath]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await verifyEmail(code.trim());
      navigate(afterVerifyPath, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    setResendNote(null);
    setResendBusy(true);
    setError(null);
    try {
      await resendVerification();
      setResendNote("New code sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setResendBusy(false);
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
          Verify your email
        </motion.h1>
        <p className="mt-2 text-sm text-lab-muted">
          Enter the 6-digit code we sent to{" "}
          <span className="text-lab-text">{user?.email}</span>.
        </p>

        {resendNote ? (
          <p className="mt-4 text-sm text-lab-accent">{resendNote}</p>
        ) : null}

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          {error ? (
            <p className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200/95">
              {error}
            </p>
          ) : null}
          <input
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="6-digit code"
            maxLength={6}
            className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-3 text-center font-mono text-lg tracking-[0.3em] text-lab-text placeholder:text-lab-subtle"
          />
          <button
            type="submit"
            disabled={busy || code.length !== 6}
            className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white disabled:opacity-60"
          >
            {busy ? "Verifying…" : "Verify"}
          </button>
        </form>

        <button
          type="button"
          onClick={() => void handleResend()}
          disabled={resendBusy}
          className="mt-6 w-full text-sm font-medium text-lab-accent hover:text-sky-300 disabled:opacity-60"
        >
          {resendBusy ? "Sending…" : "Resend code"}
        </button>
      </main>
    </div>
  );
}
