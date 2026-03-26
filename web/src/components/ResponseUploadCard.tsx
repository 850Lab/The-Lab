import { AnimatePresence, motion } from "framer-motion";
import { useId, useRef, useState } from "react";

type MockOutcome = "Deleted" | "Verified" | "Partial" | "Needs review";

const OUTCOME_COPY: Record<
  MockOutcome,
  { title: string; body: string; tone: string }
> = {
  Deleted: {
    title: "Deleted",
    body: "The bureau removed one or more items from your report as requested.",
    tone: "text-emerald-300/95 bg-emerald-500/10 border-emerald-500/20",
  },
  Verified: {
    title: "Verified",
    body: "The bureau confirmed they’re treating this as complete for now.",
    tone: "text-sky-200/95 bg-sky-500/10 border-sky-500/20",
  },
  Partial: {
    title: "Partial",
    body: "Some updates went through; we may suggest a focused follow-up.",
    tone: "text-amber-200/95 bg-amber-500/10 border-amber-500/20",
  },
  "Needs review": {
    title: "Needs review",
    body: "We’ll take a closer look and outline your best next step.",
    tone: "text-lab-text bg-white/[0.06] border-white/[0.1]",
  },
};

export function ResponseUploadCard() {
  const inputId = useId();
  const panelId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [helperOpen, setHelperOpen] = useState(false);
  const [showReviewMock, setShowReviewMock] = useState(false);
  const [mockOutcome] = useState<MockOutcome>("Partial");

  const handleFile = (file: File | null) => {
    setFileName(file ? file.name : null);
    if (file) {
      window.setTimeout(() => setShowReviewMock(true), 600);
    } else {
      setShowReviewMock(false);
    }
  };

  return (
    <motion.section
      variants={{
        hidden: { opacity: 0, y: 16 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 shadow-lg shadow-black/15 sm:px-6 sm:py-6"
    >
      <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
        Got a response?
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        Upload the page that shows their decision and we’ll guide your next
        step.
      </p>

      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf,.pdf"
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          handleFile(f ?? null);
          e.target.value = "";
        }}
      />

      <div className="mt-5">
        <AnimatePresence mode="wait">
          {fileName ? (
            <motion.div
              key="file"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.28 }}
              className="rounded-xl border border-white/[0.08] bg-lab-elevated/80 px-4 py-4"
            >
              <p className="text-xs text-lab-subtle">Selected</p>
              <p className="mt-1 truncate text-sm font-medium text-lab-text">
                {fileName}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  className="rounded-lg border border-white/[0.12] px-3 py-2 text-sm font-medium text-lab-text hover:bg-white/[0.04]"
                >
                  Replace
                </button>
                <button
                  type="button"
                  onClick={() => handleFile(null)}
                  className="rounded-lg px-3 py-2 text-sm text-lab-muted hover:bg-white/[0.04] hover:text-lab-text"
                >
                  Remove
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.label
              key="empty"
              htmlFor={inputId}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.28 }}
              className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.12] bg-lab-elevated/40 px-4 py-8 transition-colors hover:border-lab-accent/30 hover:bg-lab-elevated/60"
            >
              <span className="text-sm font-medium text-lab-text">
                Upload a photo or PDF
              </span>
              <span className="mt-1.5 text-center text-xs text-lab-subtle">
                JPG, PNG, or PDF
              </span>
              <span className="mt-5 inline-flex rounded-lg bg-lab-accent/15 px-4 py-2.5 text-sm font-semibold text-lab-accent">
                Choose file
              </span>
            </motion.label>
          )}
        </AnimatePresence>
      </div>

      <p className="mt-4 text-center text-xs leading-relaxed text-lab-subtle sm:text-sm">
        You don’t need to upload everything — just the page that shows the
        result.
      </p>

      <div className="mt-4 border-t border-white/[0.06] pt-4">
        <button
          type="button"
          aria-expanded={helperOpen}
          aria-controls={panelId}
          onClick={() => setHelperOpen((o) => !o)}
          className="flex w-full items-center justify-between gap-3 rounded-lg py-1 text-left text-sm font-medium text-lab-accent transition-colors hover:text-sky-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35"
        >
          <span>Not sure what to upload?</span>
          <motion.span
            animate={{ rotate: helperOpen ? 180 : 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="text-lab-muted"
            aria-hidden
          >
            ▼
          </motion.span>
        </button>
        <AnimatePresence initial={false}>
          {helperOpen ? (
            <motion.div
              id={panelId}
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden"
            >
              <p className="pt-3 text-sm leading-relaxed text-lab-muted">
                Upload the page that says things like verified, deleted, updated,
                or results. If you’re unsure, upload what you have and we’ll take
                a look.
              </p>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {showReviewMock && fileName ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="mt-6 rounded-xl border border-white/[0.08] bg-lab-bg/90 px-4 py-5"
          >
            <p className="text-center text-xs font-medium uppercase tracking-wide text-lab-subtle">
              We reviewed your response
            </p>
            <div
              className={`mx-auto mt-4 max-w-sm rounded-lg border px-4 py-3 text-center ${OUTCOME_COPY[mockOutcome].tone}`}
            >
              <p className="text-sm font-semibold">
                {OUTCOME_COPY[mockOutcome].title}
              </p>
              <p className="mt-1.5 text-xs leading-relaxed opacity-95 sm:text-sm">
                {OUTCOME_COPY[mockOutcome].body}
              </p>
            </div>
            <p className="mt-4 text-center text-xs text-lab-subtle">
              This is a preview — connect your backend to show live results.
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
}
