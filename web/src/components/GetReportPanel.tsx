import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ANNUAL_CREDIT_REPORT_URL } from "@/lib/reportAcquisitionConfig";

type Props = {
  open: boolean;
  onClose: () => void;
};

const BUREAUS = [
  {
    name: "Equifax",
    hint: "MyEquifax.com — free weekly report available online.",
    href: "https://www.equifax.com/personal/credit-report-services/",
  },
  {
    name: "Experian",
    hint: "Experian.com — access your report and download as PDF when offered.",
    href: "https://www.experian.com/",
  },
  {
    name: "TransUnion",
    hint: "TransUnion.com — log in and export or print to PDF.",
    href: "https://www.transunion.com/",
  },
] as const;

export function GetReportPanel({ open, onClose }: Props) {
  const [altOpen, setAltOpen] = useState(false);

  useEffect(() => {
    if (!open) setAltOpen(false);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const getReport = useCallback(() => {
    window.open(ANNUAL_CREDIT_REPORT_URL, "_blank", "noopener,noreferrer");
  }, []);

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
            transition={{ duration: 0.25 }}
            onClick={onClose}
          />
          <div className="fixed inset-0 z-[61] flex items-end justify-center p-4 sm:items-center sm:p-6">
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="get-report-title"
              className="max-h-[min(90vh,720px)] w-full max-w-lg overflow-y-auto rounded-t-2xl border border-white/[0.08] bg-lab-elevated shadow-2xl shadow-black/40 sm:rounded-2xl"
              initial={{ opacity: 0, y: 24, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="border-b border-white/[0.06] px-5 py-4 sm:px-6">
                <div className="flex items-start justify-between gap-4">
                  <h2
                    id="get-report-title"
                    className="text-lg font-semibold leading-snug text-lab-text sm:text-xl"
                  >
                    Get your credit report in minutes
                  </h2>
                  <button
                    type="button"
                    onClick={onClose}
                    className="shrink-0 rounded-md p-1 text-lab-subtle transition-colors hover:bg-white/[0.06] hover:text-lab-muted"
                  >
                    <span className="sr-only">Close</span>
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>

              <div className="space-y-5 px-5 py-5 sm:px-6">
                <p className="text-sm leading-relaxed text-lab-muted sm:text-[15px]">
                  The fastest way is to access your 3-bureau report, download it, and upload it here.
                </p>

                <button
                  type="button"
                  onClick={getReport}
                  className="w-full rounded-lg bg-lab-accent py-3 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/20 transition-shadow hover:shadow-lab-accent/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/50"
                >
                  Get my report
                </button>

                <p className="text-center text-xs text-lab-subtle sm:text-sm">
                  Recommended for the fastest, most accurate results
                </p>

                <div className="border-t border-white/[0.06] pt-4">
                  <button
                    type="button"
                    onClick={() => setAltOpen((v) => !v)}
                    className="flex w-full items-center justify-between gap-2 text-left text-sm font-medium text-lab-muted transition-colors hover:text-lab-text"
                  >
                    <span>Prefer another option?</span>
                    <motion.svg
                      className="h-4 w-4 shrink-0 text-lab-subtle"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      animate={{ rotate: altOpen ? 180 : 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </motion.svg>
                  </button>

                  <AnimatePresence initial={false}>
                    {altOpen ? (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                        className="overflow-hidden"
                      >
                        <ul className="mt-3 space-y-3 border-l border-lab-accent/25 pl-3">
                          {BUREAUS.map((b) => (
                            <li key={b.name}>
                              <a
                                href={b.href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="group block rounded-md py-1"
                              >
                                <span className="text-sm font-medium text-lab-text group-hover:text-lab-accent">
                                  {b.name}
                                </span>
                                <p className="mt-0.5 text-xs leading-relaxed text-lab-subtle">{b.hint}</p>
                              </a>
                            </li>
                          ))}
                        </ul>
                      </motion.div>
                    ) : null}
                  </AnimatePresence>
                </div>

                <p className="text-xs leading-relaxed text-lab-subtle">
                  Once you download your report, come back here and upload it to continue.
                </p>

                <div className="border-t border-white/[0.06] pt-4 text-center">
                  <Link
                    to="/get-report"
                    onClick={onClose}
                    className="text-sm font-medium text-lab-accent hover:text-sky-300"
                  >
                    View all ways to get a report (recommended + free)
                  </Link>
                </div>
              </div>
            </motion.div>
          </div>
        </>
      ) : null}
    </AnimatePresence>
  );
}
