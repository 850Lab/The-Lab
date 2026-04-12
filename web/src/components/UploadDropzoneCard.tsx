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

function ReportSheetIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 56 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M12 4h22l12 12v44H12V4z"
        className="stroke-white/20"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path d="M34 4v14h12" className="stroke-white/20" strokeWidth="1.75" strokeLinejoin="round" />
      <path
        d="M18 36h20M18 28h20M18 44h14"
        className="stroke-lab-muted/70"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

const TRUST_ITEMS = [
  { label: "Encrypted in transit" },
  { label: "Stays yours" },
  { label: "No bureau mail yet" },
] as const;

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

  const openPicker = () => {
    if (!interactive) return;
    inputRef.current?.click();
  };

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
        className={`relative overflow-hidden rounded-2xl border transition-[box-shadow,border-color,background-color] duration-500 ease-out ${
          phase === "uploading"
            ? "border-neutral-500/25 bg-gradient-to-b from-white/[0.07] via-lab-elevated to-black/[0.22] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.07),0_0_0_1px_rgba(255,255,255,0.05),0_26px_70px_-30px_rgba(0,0,0,0.58)]"
            : phase === "dragging"
              ? "border-neutral-300/55 bg-gradient-to-b from-white/[0.1] via-lab-elevated/95 to-black/[0.18] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1),0_0_0_1px_rgba(212,212,212,0.28),0_0_56px_-18px_rgba(255,255,255,0.1)]"
              : disabled
                ? "border-white/[0.06] bg-lab-elevated/50 opacity-70"
                : cardHover && phase === "idle"
                  ? "border-neutral-400/42 bg-gradient-to-b from-white/[0.06] via-lab-elevated to-black/[0.2] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08),0_0_0_1px_rgba(163,163,163,0.14),0_32px_80px_-34px_rgba(0,0,0,0.62)]"
                  : "border-neutral-600/30 bg-gradient-to-b from-white/[0.035] via-lab-elevated to-black/[0.24] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.05),0_0_0_1px_rgba(255,255,255,0.04),0_24px_64px_-30px_rgba(0,0,0,0.56)]"
        }`}
        animate={
          phase === "dragging"
            ? { scale: 1.014 }
            : interactive && cardHover
              ? { scale: 1.005 }
              : { scale: 1 }
        }
        transition={{ type: "spring", stiffness: 420, damping: 32 }}
        onMouseEnter={() => setCardHover(true)}
        onMouseLeave={() => setCardHover(false)}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={onDragOver}
        onDrop={onDrop}
      >
        <div
          className={`pointer-events-none absolute inset-0 transition-opacity duration-500 ${
            interactive && (cardHover || phase === "dragging")
              ? "opacity-100"
              : "opacity-75"
          }`}
          aria-hidden
        >
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_95%_60%_at_50%_-8%,rgba(255,255,255,0.085),transparent_58%)]" />
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neutral-400/35 to-transparent" />
        </div>

        <AnimatePresence mode="wait">
          {showDropzone ? (
            <motion.div
              key="dropzone"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="relative px-4 py-8 sm:px-8 sm:py-10"
            >
              <input
                ref={inputRef}
                type="file"
                accept=".pdf,application/pdf"
                multiple
                className="sr-only"
                disabled={!interactive}
                onChange={onInputChange}
                aria-label="Choose PDF credit report files"
              />

              <motion.button
                type="button"
                disabled={!interactive}
                onClick={openPicker}
                whileTap={interactive ? { scale: 0.992 } : undefined}
                transition={{ type: "spring", stiffness: 520, damping: 28 }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    openPicker();
                  }
                }}
                className={`group relative flex w-full min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed px-4 py-8 text-center transition-[border-color,background-color,box-shadow] duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20 focus-visible:ring-offset-2 focus-visible:ring-offset-lab-bg disabled:pointer-events-none disabled:opacity-45 sm:min-h-[220px] ${
                  phase === "dragging"
                    ? "border-neutral-300/55 bg-black/22 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]"
                    : "border-white/[0.12] bg-black/[0.14] shadow-[inset_0_2px_12px_rgba(0,0,0,0.2)] hover:border-neutral-400/45 hover:bg-black/[0.18] hover:shadow-[inset_0_2px_16px_rgba(0,0,0,0.22)]"
                }`}
              >
                <motion.div
                  animate={{
                    y: phase === "dragging" ? -3 : cardHover && !disabled ? -2 : 0,
                    scale: phase === "dragging" ? 1.05 : cardHover && !disabled ? 1.03 : 1,
                  }}
                  transition={{ type: "spring", stiffness: 400, damping: 22 }}
                >
                  <ReportSheetIcon className="h-14 w-12 text-neutral-200/90 sm:h-16 sm:w-14" />
                </motion.div>

                <motion.span
                  className="mt-4 block text-xl font-bold tracking-tight text-lab-text sm:text-2xl"
                  animate={{
                    y: phase === "dragging" ? 1 : cardHover && !disabled ? -1 : 0,
                  }}
                  transition={{ type: "spring", stiffness: 380, damping: 24 }}
                >
                  {disabled ? "Almost there — confirm above" : "Drop your report here"}
                </motion.span>
                <span className="mt-2 block max-w-md text-pretty text-sm font-medium leading-relaxed text-lab-muted">
                  {disabled
                    ? "Check the box, then drop your file or tap — we take it from there."
                    : "Easiest step — release it or tap to browse. We organize everything from here."}
                </span>

                <span className="mt-4 inline-flex items-center rounded-full border border-white/[0.1] bg-white/[0.04] px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-lab-subtle sm:text-xs">
                  PDF · single bureau
                </span>

                <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                  {[
                    { k: "Parts", v: "≤25 MB" },
                    { k: "Bundle", v: "≤12 files" },
                    { k: "Single", v: "≤200 MB" },
                  ].map((row) => (
                    <span
                      key={row.k}
                      className="inline-flex items-baseline gap-1 rounded-md border border-white/[0.08] bg-black/25 px-2 py-1 text-[10px] sm:gap-1.5 sm:px-2.5 sm:py-1.5 sm:text-[11px]"
                    >
                      <span className="font-bold uppercase tracking-[0.1em] text-neutral-400">{row.k}</span>
                      <span className="text-lab-muted">{row.v}</span>
                    </span>
                  ))}
                </div>

                {labelHint && phase === "idle" ? (
                  <motion.p
                    className="mt-3 max-w-full rounded-md border border-white/[0.06] bg-white/[0.03] px-2 py-1.5 text-[11px] text-lab-subtle sm:px-3 sm:py-2 sm:text-xs"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <span className="line-clamp-2 break-all">{labelHint}</span>
                  </motion.p>
                ) : null}

                {error ? (
                  <p
                    className="mt-3 max-w-md rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200/95 sm:text-sm"
                    role="alert"
                  >
                    {error}
                  </p>
                ) : null}
              </motion.button>

              <p className="mx-auto mt-4 max-w-md text-pretty text-center text-[10px] leading-relaxed text-lab-subtle sm:text-[11px]">
                Multi-part exports: name files{" "}
                <span className="font-medium text-lab-muted/90">report_01.pdf</span>,{" "}
                <span className="font-medium text-lab-muted/90">report_02.pdf</span> so page order stays
                correct.
              </p>
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
                <p className="pt-4 text-center text-[11px] font-medium text-lab-subtle line-clamp-2 sm:pt-5 sm:text-xs">
                  {partCount > 1 ? `${partCount} parts` : "1 file"} · {labelHint}
                </p>
              ) : null}
              <UploadProgressState
                compact
                title={
                  partCount > 1
                    ? "Putting your report together…"
                    : "Working through your report…"
                }
                subtitle="We’re already finding what deserves your attention — usually under a minute."
              />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {showDropzone ? (
        <motion.p
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08, duration: 0.35 }}
          className="mt-4 flex flex-wrap items-center justify-center gap-x-1 gap-y-1 text-center text-[11px] font-medium tracking-wide text-lab-muted sm:mt-5 sm:text-xs"
          role="group"
          aria-label="Upload assurances"
        >
          {TRUST_ITEMS.map((item, i) => (
            <span key={item.label} className="inline-flex items-center gap-x-1">
              {i > 0 ? (
                <span className="px-1 text-neutral-500/45" aria-hidden>
                  ·
                </span>
              ) : null}
              <span className="text-neutral-400/95">{item.label}</span>
            </span>
          ))}
        </motion.p>
      ) : null}
    </motion.div>
  );
}
