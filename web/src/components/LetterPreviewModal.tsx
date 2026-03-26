import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  bureau: string;
  body: string;
};

export function LetterPreviewModal({ open, onClose, bureau, body }: Props) {
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

  return (
    <AnimatePresence>
      {open ? (
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
            aria-labelledby="letter-preview-title"
            className="relative z-10 flex max-h-[min(85vh,640px)] w-full max-w-lg flex-col overflow-hidden rounded-xl border border-white/[0.1] bg-lab-elevated shadow-2xl shadow-black/50"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-4 sm:px-6">
              <h2
                id="letter-preview-title"
                className="text-[15px] font-semibold text-lab-text"
              >
                {bureau} letter
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
              <div className="rounded-lg border border-white/[0.06] bg-lab-bg/80 px-4 py-5 sm:px-5 sm:py-6">
                <pre className="whitespace-pre-wrap font-sans text-[13px] leading-[1.65] text-lab-text/95 sm:text-[14px]">
                  {body}
                </pre>
              </div>
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
