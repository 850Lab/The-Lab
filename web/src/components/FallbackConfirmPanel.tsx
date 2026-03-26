import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  onContinue: () => void;
};

export function FallbackConfirmPanel({ open, onClose, onContinue }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.button
            type="button"
            aria-label="Close"
            className="fixed inset-0 z-[60] bg-lab-bg/80 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            onClick={onClose}
          />
          <div className="fixed inset-0 z-[61] flex items-center justify-center p-4 sm:p-6">
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="fallback-title"
              className="w-full max-w-md rounded-2xl border border-white/[0.08] bg-lab-elevated p-6 shadow-2xl shadow-black/40 sm:p-7"
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 6 }}
              transition={{ type: "spring", stiffness: 420, damping: 34 }}
              onClick={(e) => e.stopPropagation()}
            >
              <h2 id="fallback-title" className="text-lg font-semibold text-lab-text sm:text-xl">
                We can still get started
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-lab-muted sm:text-[15px]">
                Answer a few quick questions and we’ll prepare a basic dispute path while you work on
                getting your full report.
              </p>
              <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg border border-white/[0.1] bg-transparent px-4 py-2.5 text-sm font-medium text-lab-muted transition-colors hover:border-white/[0.14] hover:bg-white/[0.04] hover:text-lab-text"
                >
                  Go back
                </button>
                <button
                  type="button"
                  onClick={onContinue}
                  className="rounded-lg bg-lab-accent px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-lab-accent/20 transition-shadow hover:shadow-lab-accent/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/50"
                >
                  Continue
                </button>
              </div>
            </motion.div>
          </div>
        </>
      ) : null}
    </AnimatePresence>
  );
}
