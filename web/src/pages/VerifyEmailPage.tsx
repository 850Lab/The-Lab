import { motion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { afterVerifyProgramLine } from "@/lib/programEntryContinuation";
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
  const sendInitialCodeFromNav = Boolean(locState?.sendInitialCode);
  let sendInitialFromStorage = false;
  try {
    sendInitialFromStorage =
      sessionStorage.getItem("850lab_verify_send_initial") === "1";
  } catch {
    sendInitialFromStorage = false;
  }
  const wantsInitialSend = sendInitialCodeFromNav || sendInitialFromStorage;
  const afterVerifyPath = safeAppPath(locState?.returnTo) ?? "/";
  const afterVerifyLine = afterVerifyProgramLine(afterVerifyPath);

  useEffect(() => {
    if (!wantsInitialSend || initialSendRef.current) return;
    initialSendRef.current = true;
    void (async () => {
      try {
        await resendVerification();
        setResendNote("We sent a code to your email.");
        try {
          sessionStorage.removeItem("850lab_verify_send_initial");
        } catch {
          /* ignore */
        }
      } catch (err) {
        try {
          sessionStorage.removeItem("850lab_verify_send_initial");
        } catch {
          /* ignore */
        }
        setResendNote("We could not send the email automatically.");
        setError(
          err instanceof Error ? err.message : String(err),
        );
      }
    })();
  }, [wantsInitialSend, resendVerification]);

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
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-accent">
          Your program · Verify email
        </p>
        <motion.h1
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-2 text-2xl font-semibold text-lab-text"
        >
          Confirm your email to continue
        </motion.h1>
        <p className="mt-2 text-sm leading-relaxed text-lab-muted">
          We need a verified email to continue your program — the same secure inbox we&apos;ll use
          for important updates. Enter the 6-digit code we sent to{" "}
          <span className="text-lab-text">{user?.email || "your email"}</span>.
        </p>
        <div className="mt-4 rounded-xl border border-white/[0.1] bg-lab-surface/50 px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-lab-muted">What&apos;s next</p>
          <p className="mt-1.5 text-sm leading-relaxed text-lab-muted">{afterVerifyLine}</p>
        </div>
        <p className="mt-4 text-sm text-lab-muted">
          No message yet? Check spam, then tap <span className="text-lab-text">Resend code</span>.
        </p>
        <p className="mt-2 text-xs text-lab-subtle">
          Local dev: the workflow API should be running (often{" "}
          <span className="text-lab-text">127.0.0.1:8000</span>) for codes to send.
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
            {busy ? "Verifying…" : "Confirm & continue"}
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
