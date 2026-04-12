import { useCallback, useState } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { submitPublicDemoLead } from "@/lib/publicDemoApi";
import { WAITLIST_LEAD_INTENT } from "@/lib/productGates";

type Mode = "open" | "waitlist";

type Props = {
  open: boolean;
  onClose: () => void;
  mode: Mode;
};

const field =
  "mt-1.5 w-full rounded-lg border border-white/[0.12] bg-lab-bg/60 px-3 py-2.5 text-sm text-lab-text outline-none transition-colors placeholder:text-lab-subtle focus:border-zinc-500/50 focus:ring-2 focus:ring-zinc-500/25";

function resolvedName(name: string, email: string): string {
  const t = name.trim();
  if (t.length >= 2) return t;
  const local = email.trim().split("@")[0]?.replace(/[.+_]/g, " ").trim() ?? "";
  return local.length >= 2 ? local : "";
}

/**
 * Lightweight lead capture: reuses public demo lead API (no new backend).
 * Open mode: intent try_myself, then user can continue to /get-report.
 * Waitlist: same payload shape as WaitlistLeadForm (intent + phone required).
 */
export function LandingEarlyAccessModal({ open, onClose, mode }: Props) {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const reset = useCallback(() => {
    setErr(null);
    setBusy(false);
    setDone(false);
  }, []);

  const handleClose = useCallback(() => {
    reset();
    setName("");
    setEmail("");
    setPhone("");
    onClose();
  }, [onClose, reset]);

  const submit = useCallback(async () => {
    setErr(null);
    const em = email.trim();
    const ph = phone.trim();
    const resolved = resolvedName(name, em);
    if (!em.includes("@") || em.length < 5) {
      setErr("Enter a valid email.");
      return;
    }
    if (resolved.length < 2) {
      setErr("Add your name (or a recognizable part of your email before @).");
      return;
    }
    if (mode === "waitlist") {
      if (ph.length < 7) {
        setErr("Phone required so we can reach you when access opens.");
        return;
      }
    }
    setBusy(true);
    try {
      await submitPublicDemoLead({
        name: resolved,
        email: em,
        phone: mode === "waitlist" ? ph : ph.length >= 7 ? ph : "not-provided-yet",
        intent: mode === "waitlist" ? WAITLIST_LEAD_INTENT : "try_myself",
      });
      setDone(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [email, name, phone, mode]);

  const continueToReport = useCallback(() => {
    handleClose();
    navigate("/get-report");
  }, [handleClose, navigate]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-[100] flex items-end justify-center p-4 sm:items-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <button
            type="button"
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            aria-label="Close"
            onClick={handleClose}
          />
          <motion.div
            role="dialog"
            aria-modal
            aria-labelledby="early-access-title"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-[101] w-full max-w-md overflow-hidden rounded-2xl border border-white/[0.12] bg-lab-surface shadow-2xl shadow-black/50"
          >
            <div className="border-b border-white/[0.06] px-5 py-4 sm:px-6">
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-lab-subtle">
                {mode === "waitlist" ? "Request access" : "Early access"}
              </p>
              <h2 id="early-access-title" className="mt-1 font-heading text-lg font-semibold text-white">
                Get access
              </h2>
              <p className="mt-1 text-sm text-lab-muted">
                {mode === "waitlist"
                  ? "We’re opening in waves. Leave a line — we’ll reach you."
                  : "Tell us who you are. Then continue into the report flow."}
              </p>
            </div>

            {done ? (
              <div className="space-y-4 px-5 py-8 sm:px-6">
                <p className="text-center text-sm font-medium text-lab-text">
                  {mode === "waitlist"
                    ? "Received. We’ll be in touch."
                    : "You’re set — continue when you’re ready."}
                </p>
                <div className="flex flex-col gap-2">
                  {mode === "open" ? (
                    <button
                      type="button"
                      onClick={continueToReport}
                      className="rounded-lg bg-white py-3 text-sm font-bold text-lab-bg hover:bg-neutral-100"
                    >
                      Run Your Report
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={handleClose}
                    className="rounded-lg border border-white/[0.12] py-3 text-sm font-semibold text-lab-text hover:bg-white/[0.04]"
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4 px-5 py-6 sm:px-6">
                <div>
                  <label htmlFor="ea-name" className="text-xs font-semibold text-lab-muted">
                    Name
                  </label>
                  <input
                    id="ea-name"
                    autoComplete="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className={field}
                    placeholder="Your name"
                  />
                </div>
                <div>
                  <label htmlFor="ea-email" className="text-xs font-semibold text-lab-muted">
                    Email
                  </label>
                  <input
                    id="ea-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={field}
                    placeholder="you@domain.com"
                  />
                </div>
                <div>
                  <label htmlFor="ea-phone" className="text-xs font-semibold text-lab-muted">
                    Phone {mode === "open" ? <span className="font-normal text-lab-subtle">(optional)</span> : null}
                  </label>
                  <input
                    id="ea-phone"
                    type="tel"
                    autoComplete="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className={field}
                    placeholder={mode === "waitlist" ? "Best number to reach you" : "Optional"}
                  />
                </div>
                {err ? <p className="text-sm font-medium text-rose-300/90">{err}</p> : null}
                <div className="flex flex-col gap-2 pt-1">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void submit()}
                    className="rounded-lg bg-lab-accent py-3 text-sm font-bold text-white shadow-md shadow-black/30 hover:brightness-110 disabled:opacity-50"
                  >
                    {busy ? "Sending…" : mode === "waitlist" ? "Request access" : "Submit & continue"}
                  </button>
                  <button
                    type="button"
                    onClick={handleClose}
                    className="py-2 text-sm font-medium text-lab-muted hover:text-lab-text"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
}
