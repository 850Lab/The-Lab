import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useRef, useState } from "react";
import { UploadProgressState } from "@/components/UploadProgressState";

type UploadResult =
  | { success: true }
  | { success: false; message: string };

type Props = {
  disabled?: boolean;
  onUploadPdfs: (files: File[]) => Promise<UploadResult>;
};

function isPdfFile(f: File) {
  return f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
}

function pdfFilesFromFileList(fileList: FileList | null): File[] {
  if (!fileList?.length) return [];
  const out: File[] = [];
  for (let i = 0; i < fileList.length; i++) {
    const f = fileList.item(i);
    if (f) out.push(f);
  }
  return out.sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }),
  );
}

function summarizeNames(files: File[], max = 3): string {
  if (files.length === 0) return "";
  if (files.length === 1) return files[0].name;
  const shown = files.slice(0, max).map((f) => f.name);
  const more = files.length > max ? ` +${files.length - max} more` : "";
  return `${shown.join(", ")}${more}`;
}

function MergeStackIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 64 56"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <rect x="8" y="4" width="48" height="36" rx="3" className="stroke-white/25" strokeWidth="1.5" />
      <rect x="4" y="12" width="48" height="36" rx="3" className="stroke-lab-accent/50" strokeWidth="1.5" />
      <rect
        x="0"
        y="20"
        width="48"
        height="36"
        rx="3"
        className="fill-lab-surface stroke-lab-accent"
        strokeWidth="2"
      />
      <path
        d="M14 38h20M14 32h14"
        className="stroke-lab-muted/80"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function UploadDropzoneCard({ disabled, onUploadPdfs }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<"idle" | "dragging" | "uploading">("idle");
  const [pendingFiles, setPendingFiles] = useState<File[] | null>(null);
  const [labelHint, setLabelHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cardHover, setCardHover] = useState(false);
  const dragDepth = useRef(0);

  const resetError = useCallback(() => setError(null), []);

  const runUpload = useCallback(
    async (files: File[]) => {
      resetError();
      setPendingFiles(files);
      setLabelHint(summarizeNames(files));
      setPhase("uploading");
      const result = await onUploadPdfs(files);
      if (!result.success) {
        setError(result.message);
        setPhase("idle");
        setLabelHint(null);
        setPendingFiles(null);
        return;
      }
    },
    [onUploadPdfs, resetError],
  );

  const handleFiles = useCallback(
    (picked: File[]) => {
      if (disabled || phase === "uploading") return;
      resetError();
      if (!picked.length) return;
      const nonPdf = picked.filter((f) => !isPdfFile(f));
      if (nonPdf.length) {
        setError("Every selected file must be a PDF.");
        setPhase("idle");
        return;
      }
      void runUpload(picked);
    },
    [disabled, phase, resetError, runUpload],
  );

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const list = pdfFilesFromFileList(e.target.files);
    handleFiles(list);
    e.target.value = "";
  };

  const onDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled || phase === "uploading") return;
    dragDepth.current += 1;
    if (!e.dataTransfer.types.includes("Files")) return;
    setPhase((p) => (p === "uploading" ? p : "dragging"));
  };

  const onDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current -= 1;
    if (dragDepth.current <= 0) {
      dragDepth.current = 0;
      setPhase((p) => (p === "dragging" ? "idle" : p));
    }
  };

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes("Files")) e.dataTransfer.dropEffect = "copy";
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current = 0;
    if (phase === "uploading" || disabled) return;
    const list = pdfFilesFromFileList(e.dataTransfer.files);
    handleFiles(list);
  };

  const showDropzone = phase !== "uploading";
  const interactive = !disabled && (phase === "idle" || phase === "dragging");
  const partCount = pendingFiles?.length ?? 0;

  return (
    <motion.div
      layout
      className="relative w-full"
      transition={{ layout: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } }}
    >
      <motion.div
        layout
        role="region"
        aria-label="PDF upload"
        className={`relative overflow-hidden rounded-2xl border-2 transition-[box-shadow,border-color,background] duration-300 ${
          phase === "uploading"
            ? "border-lab-accent/35 bg-gradient-to-b from-lab-accent/[0.08] to-lab-elevated shadow-[0_0_56px_-20px_rgba(56,189,248,0.45)]"
            : phase === "dragging"
              ? "border-lab-accent bg-gradient-to-b from-lab-accent/[0.12] to-lab-elevated shadow-[0_0_0_1px_rgba(56,189,248,0.4),0_0_60px_-12px_rgba(56,189,248,0.35)]"
              : disabled
                ? "border-white/[0.06] bg-lab-elevated/60 opacity-75"
                : cardHover && phase === "idle"
                  ? "border-white/[0.14] bg-lab-elevated shadow-[0_20px_50px_-24px_rgba(0,0,0,0.65)]"
                  : "border-white/[0.1] bg-gradient-to-b from-lab-elevated to-lab-surface/30 shadow-[0_24px_64px_-28px_rgba(0,0,0,0.55)]"
        }`}
        animate={phase === "dragging" ? { scale: 1.008 } : { scale: 1 }}
        transition={{ type: "spring", stiffness: 420, damping: 30 }}
        onMouseEnter={() => setCardHover(true)}
        onMouseLeave={() => setCardHover(false)}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={onDragOver}
        onDrop={onDrop}
      >
        <div
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,rgba(56,189,248,0.14),transparent)]"
          aria-hidden
        />

        <AnimatePresence mode="wait">
          {showDropzone ? (
            <motion.div
              key="dropzone"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="relative px-4 py-5 sm:px-6 sm:py-6"
            >
              <div className="flex flex-col items-center text-center">
                <div className="flex items-center gap-2">
                  <MergeStackIcon className="h-9 w-11 shrink-0 text-lab-accent sm:h-10 sm:w-[2.85rem]" />
                </div>

                <h3 className="mt-2.5 text-lg font-bold tracking-tight text-lab-text sm:mt-3 sm:text-xl">
                  {disabled ? "Confirm privacy below to upload" : "Drop PDFs here — we turn them into one report"}
                </h3>
                <p className="mt-1 max-w-md text-pretty text-xs font-medium leading-snug text-lab-muted sm:mt-1.5 sm:text-sm sm:leading-relaxed">
                  {disabled
                    ? "Check the consent box, then upload."
                    : "One large bureau file (we split & merge on our servers) or several parts — same pipeline either way."}
                </p>

                <div className="mt-2.5 flex flex-wrap items-center justify-center gap-1.5 sm:mt-3 sm:gap-2">
                  {[
                    { k: "Parts", v: "≤25 MB each" },
                    { k: "Bundle", v: "Up to 12 PDFs" },
                    { k: "Single", v: "≤200 MB" },
                  ].map((row) => (
                    <span
                      key={row.k}
                      className="inline-flex items-baseline gap-1 rounded-full border border-white/[0.1] bg-black/20 px-2 py-1 text-[10px] sm:gap-1.5 sm:px-2.5 sm:py-1.5 sm:text-[11px]"
                    >
                      <span className="font-bold uppercase tracking-[0.12em] text-lab-accent">{row.k}</span>
                      <span className="text-lab-muted">{row.v}</span>
                    </span>
                  ))}
                </div>

                {labelHint && phase === "idle" ? (
                  <motion.p
                    className="mt-2 max-w-full rounded-md border border-white/[0.06] bg-white/[0.03] px-2 py-1.5 text-[11px] text-lab-subtle sm:mt-2.5 sm:px-3 sm:py-2 sm:text-xs"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <span className="line-clamp-2 break-all">{labelHint}</span>
                  </motion.p>
                ) : null}

                {error ? (
                  <p className="mt-2 rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-xs text-red-200/95 sm:mt-2.5 sm:px-3 sm:py-2 sm:text-sm" role="alert">
                    {error}
                  </p>
                ) : null}

                <motion.div
                  className="mt-4 w-full max-w-xs sm:mt-5 sm:max-w-sm"
                  whileHover={interactive && phase === "idle" ? { scale: 1.02 } : undefined}
                  whileTap={interactive && phase === "idle" ? { scale: 0.98 } : undefined}
                >
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    multiple
                    className="hidden"
                    disabled={!interactive}
                    onChange={onInputChange}
                  />
                  <button
                    type="button"
                    disabled={!interactive}
                    onClick={() => inputRef.current?.click()}
                    className="w-full rounded-xl bg-lab-accent py-3 text-sm font-bold text-white shadow-lg shadow-lab-accent/30 transition-[box-shadow,filter] hover:brightness-110 hover:shadow-lab-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/60 focus-visible:ring-offset-2 focus-visible:ring-offset-lab-bg disabled:pointer-events-none disabled:opacity-40 sm:py-3.5 sm:text-base"
                  >
                    Choose PDF file(s)
                  </button>
                </motion.div>

                <p className="mt-3 max-w-sm text-pretty text-[10px] leading-snug text-lab-subtle sm:mt-3.5 sm:text-[11px] sm:leading-relaxed">
                  Multi-part: use names like <span className="font-medium text-lab-muted">report_01.pdf</span>,{" "}
                  <span className="font-medium text-lab-muted">report_02.pdf</span> so sort order matches your
                  pages. We merge, then parse as <span className="font-semibold text-lab-text/90">one bureau report</span>.
                </p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="processing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              className="relative px-4 sm:px-6"
            >
              {labelHint ? (
                <p className="pt-3 text-center text-[11px] font-medium text-lab-subtle line-clamp-2 sm:pt-4 sm:text-xs">
                  {partCount > 1 ? `${partCount} parts` : "1 file"} · {labelHint}
                </p>
              ) : null}
              <UploadProgressState
                compact
                title={partCount > 1 ? "Merging parts & parsing…" : "Uploading & parsing…"}
                subtitle="Building one report for analysis — keep this tab open."
              />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}
