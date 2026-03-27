import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";
import type { TrackingModalBureau } from "@/lib/trackingTypes";

type Props = {
  open: boolean;
  onClose: () => void;
  bureau: TrackingModalBureau | null;
};

function formatWhen(iso: string): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(t));
}

export function TrackingDetailsModal({ open, onClose, bureau }: Props) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const hasUspsLink = Boolean(bureau?.trackingUrl?.trim());
  const hasNumber = Boolean(bureau?.trackingNumber?.trim());

  return (
    <AnimatePresence>
      {open && bureau ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center sm:p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.28 }}
          role="presentation"
        >
          <motion.div
            role="presentation"
            className="absolute inset-0 cursor-default bg-black/65 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="tracking-modal-title"
            className="relative z-10 flex max-h-[min(88vh,680px)] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-white/[0.1] bg-lab-elevated shadow-2xl shadow-black/50"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-4 sm:px-6">
              <h2
                id="tracking-modal-title"
                className="text-[15px] font-semibold text-lab-text"
              >
                {bureau.bureauDisplay} — mail status
              </h2>
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg px-2.5 py-1.5 text-sm text-lab-muted transition-colors hover:bg-white/[0.06] hover:text-lab-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/40"
              >
                Close
              </button>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
              <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                Status
              </p>
              <p className="mt-2 text-sm text-lab-text">{bureau.displayStatus}</p>

              {bureau.rowStatus === "mailed" && bureau.isTestSend ? (
                <p className="mt-4 text-sm leading-relaxed text-amber-200/90">
                  This row is a <span className="font-semibold">Lob test</span> send. No physical
                  letter entered USPS; do not expect bureau delivery from this submission.
                </p>
              ) : null}

              {bureau.rowStatus === "mailed" && !bureau.isTestSend ? (
                <p className="mt-4 text-sm leading-relaxed text-lab-muted">
                  Live submission: the processor accepted the piece for mailing. USPS tracking (if
                  shown) reflects carrier scans — not proof the bureau processed your dispute.
                </p>
              ) : null}

              {bureau.rowStatus === "error" && bureau.errorMessage ? (
                <div className="mt-5 rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-amber-200/90">
                    Send issue
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-lab-text">
                    {bureau.errorMessage}
                  </p>
                </div>
              ) : null}

              {bureau.rowStatus === "not_mailed" ? (
                <p className="mt-5 text-sm leading-relaxed text-lab-muted">
                  No certified send is recorded for this bureau yet. Finish mailing from
                  the send step, then refresh this page.
                </p>
              ) : null}

              {bureau.rowStatus === "other" && bureau.lobDbStatus ? (
                <p className="mt-5 text-sm leading-relaxed text-lab-muted">
                  Last recorded Lob status:{" "}
                  <span className="font-medium text-lab-text">{bureau.lobDbStatus}</span>
                  . Tracking may appear once the piece is marked mailed.
                </p>
              ) : null}

              {bureau.lobId?.trim() ? (
                <div className="mt-5 rounded-xl border border-white/[0.08] bg-lab-bg/80 px-4 py-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                    Processor reference (Lob)
                  </p>
                  <p className="mt-2 break-all font-mono text-sm text-lab-text">{bureau.lobId}</p>
                </div>
              ) : null}

              {bureau.mailedAt ? (
                <div className="mt-4 rounded-xl border border-white/[0.08] bg-lab-bg/80 px-4 py-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                    Submission recorded
                  </p>
                  <p className="mt-2 text-sm text-lab-text">{formatWhen(bureau.mailedAt)}</p>
                </div>
              ) : null}

              {bureau.expectedDelivery ? (
                <div className="mt-4 rounded-xl border border-white/[0.08] bg-lab-bg/80 px-4 py-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                    Expected delivery (from processor)
                  </p>
                  <p className="mt-2 text-sm text-lab-text">{bureau.expectedDelivery}</p>
                </div>
              ) : null}

              {hasNumber ? (
                <div className="mt-4 rounded-xl border border-white/[0.08] bg-lab-bg/80 px-4 py-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                    USPS tracking number
                  </p>
                  <p className="mt-2 break-all font-mono text-sm text-lab-text">
                    {bureau.trackingNumber}
                  </p>
                </div>
              ) : null}

              {hasUspsLink ? (
                <a
                  href={bureau.trackingUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-6 flex w-full items-center justify-center rounded-lg bg-lab-accent/20 py-3 text-sm font-semibold text-lab-accent transition-colors hover:bg-lab-accent/28"
                >
                  Open USPS tracking
                </a>
              ) : null}

              {!hasUspsLink && bureau.rowStatus === "mailed" && !hasNumber ? (
                <p className="mt-5 text-sm text-lab-muted">
                  A tracking number is not on file yet; check back after the send is fully
                  processed.
                </p>
              ) : null}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
