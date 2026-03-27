import { AnimatePresence, motion } from "framer-motion";
import { useId, useRef, type ReactNode } from "react";

export type UploadRequirementCardProps = {
  title: string;
  supportText: string;
  examples?: ReactNode;
  footerSlot?: ReactNode;
  fileName: string | null;
  complete: boolean;
  onFileSelected: (file: File) => void;
  onClearFile: () => void;
  accept?: string;
  /** When a local file is chosen, optional second step to upload to the server. */
  onCommit?: () => void;
  commitLabel?: string;
  commitBusy?: boolean;
};

export function UploadRequirementCard({
  title,
  supportText,
  examples,
  footerSlot,
  fileName,
  complete,
  onFileSelected,
  onClearFile,
  accept = "image/jpeg,image/png,image/webp,application/pdf,.pdf",
  onCommit,
  commitLabel = "Save to account",
  commitBusy,
}: UploadRequirementCardProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

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
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
            {title}
          </h3>
          <p className="mt-1.5 text-sm leading-relaxed text-lab-muted">
            {supportText}
          </p>
        </div>
        <AnimatePresence mode="wait">
          {complete ? (
            <motion.span
              key="ok"
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="flex h-8 shrink-0 items-center rounded-full bg-emerald-500/12 px-2.5 text-xs font-medium text-emerald-300/95"
            >
              Added
            </motion.span>
          ) : null}
        </AnimatePresence>
      </div>

      {examples ? (
        <div className="mt-3 rounded-lg border border-white/[0.05] bg-lab-elevated/60 px-3.5 py-3 text-sm text-lab-muted">
          <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
            Examples
          </p>
          <div className="mt-2">{examples}</div>
        </div>
      ) : null}

      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFileSelected(f);
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
              className="flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-lab-elevated/80 px-4 py-4 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="text-xs text-lab-subtle">Selected</p>
                <p className="truncate text-sm font-medium text-lab-text">
                  {fileName}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => inputRef.current?.click()}
                  className="rounded-lg border border-white/[0.12] px-3 py-2 text-sm font-medium text-lab-text transition-colors hover:bg-white/[0.05]"
                >
                  Replace
                </button>
                <button
                  type="button"
                  onClick={onClearFile}
                  className="rounded-lg px-3 py-2 text-sm text-lab-muted transition-colors hover:bg-white/[0.04] hover:text-lab-text"
                >
                  Remove
                </button>
              </div>
              {onCommit ? (
                <button
                  type="button"
                  onClick={onCommit}
                  disabled={commitBusy}
                  className="mt-3 w-full rounded-lg bg-lab-accent/20 py-2.5 text-sm font-semibold text-lab-accent transition-colors hover:bg-lab-accent/28 disabled:pointer-events-none disabled:opacity-45"
                >
                  {commitBusy ? "Saving…" : commitLabel}
                </button>
              ) : null}
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.28 }}
            >
              <label
                htmlFor={inputId}
                className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.12] bg-lab-elevated/40 px-4 py-8 transition-colors hover:border-lab-accent/30 hover:bg-lab-elevated/70"
              >
                <span className="text-sm font-medium text-lab-text">
                  Upload a photo or PDF
                </span>
                <span className="mt-1.5 text-center text-xs text-lab-subtle">
                  JPG, PNG, or PDF — keep it clear and readable
                </span>
                <span className="mt-5 inline-flex rounded-lg bg-lab-accent/15 px-4 py-2.5 text-sm font-semibold text-lab-accent">
                  Choose file
                </span>
              </label>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {footerSlot}
    </motion.section>
  );
}
