import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";
import type { BureauTrackingInfo } from "@/lib/mockTrackingData";

type Props = {
  open: boolean;
  onClose: () => void;
  bureau: BureauTrackingInfo | null;
};

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

  const ready = bureau?.trackingReady && bureau.trackingNumber && bureau.events;

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
                {bureau.name} — tracking
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
              {!ready ? (
                <div className="rounded-xl border border-white/[0.06] bg-lab-bg/80 px-4 py-10 text-center">
                  <p className="text-sm font-medium text-lab-text">
                    Tracking will appear shortly
                  </p>
                  <p className="mx-auto mt-2 max-w-xs text-sm leading-relaxed text-lab-muted">
                    We’re finishing the handoff for this bureau. Check back soon
                    — your letter is already on its way.
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  <div className="rounded-xl border border-white/[0.08] bg-lab-bg/80 px-4 py-4">
                    <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                      Tracking number
                    </p>
                    <p className="mt-2 break-all font-mono text-sm text-lab-text">
                      {bureau.trackingNumber}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                      Status updates
                    </p>
                    <ul className="mt-4 space-y-0">
                      {bureau.events!.map((ev, i) => (
                        <li
                          key={`${ev.at}-${i}`}
                          className="relative border-l border-white/[0.1] py-3 pl-5 first:pt-0 last:pb-0"
                        >
                          <span
                            className="absolute -left-[5px] top-[1.15rem] h-2.5 w-2.5 rounded-full border-2 border-lab-bg bg-lab-accent first:top-3"
                            aria-hidden
                          />
                          <p className="text-xs text-lab-subtle">{ev.at}</p>
                          <p className="mt-1 text-sm text-lab-text">{ev.label}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
