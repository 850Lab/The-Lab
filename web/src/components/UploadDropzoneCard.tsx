import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useRef, useState } from "react";
import { UploadProgressState } from "@/components/UploadProgressState";

type UploadPhase = "idle" | "dragging" | "selected" | "uploading" | "analyzing";

function isPdfFile(f: File) {
  return f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf");
}

export function UploadDropzoneCard() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [fileName, setFileName] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [cardHover, setCardHover] = useState(false);
  const dragDepth = useRef(0);

  const resetError = useCallback(() => setError(null), []);

  const runUploadSimulation = useCallback((name: string) => {
    setFileName(name);
    setPhase("uploading");
    setProgress(0);
    const start = performance.now();
    const duration = 1400;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setProgress(Math.round(t * 100));
      if (t < 1) {
        requestAnimationFrame(tick);
      } else {
        setPhase("analyzing");
      }
    };
    requestAnimationFrame(tick);
  }, []);

  const handleFile = useCallback(
    (file: File | null) => {
      resetError();
      if (!file) return;
      if (!isPdfFile(file)) {
        setError("Please upload a PDF file.");
        setPhase("idle");
        return;
      }
      setPhase("selected");
      setFileName(file.name);
      window.setTimeout(() => runUploadSimulation(file.name), 450);
    },
    [resetError, runUploadSimulation]
  );

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    handleFile(f);
    e.target.value = "";
  };

  const onDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragDepth.current += 1;
    if (!e.dataTransfer.types.includes("Files")) return;
    setPhase((p) => {
      if (p === "analyzing" || p === "selected" || p === "uploading") return p;
      return "dragging";
    });
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
    if (phase === "analyzing") return;
    const f = e.dataTransfer.files?.[0] ?? null;
    handleFile(f);
  };

  const showDropzone = phase !== "analyzing";
  const interactive = phase === "idle" || phase === "dragging" || phase === "selected";

  return (
    <motion.div
      layout
      className="relative w-full max-w-lg"
      transition={{ layout: { duration: 0.45, ease: [0.22, 1, 0.36, 1] } }}
    >
      <motion.div
        layout
        className={`relative overflow-hidden rounded-2xl border bg-lab-elevated transition-[box-shadow,border-color] duration-300 ${
          phase === "analyzing"
            ? "border-lab-accent/20 shadow-[0_0_40px_-16px_rgba(59,130,246,0.25)]"
            : phase === "dragging"
              ? "border-lab-accent/55 shadow-[0_0_0_1px_rgba(59,130,246,0.35),0_0_48px_-12px_rgba(59,130,246,0.35)]"
              : cardHover && phase === "idle"
                ? "border-white/[0.12] shadow-[0_0_36px_-14px_rgba(59,130,246,0.22)] shadow-xl shadow-black/25"
                : "border-white/[0.08] shadow-xl shadow-black/20"
        }`}
        animate={
          phase === "dragging"
            ? { scale: 1.01 }
            : phase === "idle"
              ? { scale: 1 }
              : { scale: 1 }
        }
        transition={{ type: "spring", stiffness: 400, damping: 28 }}
        onMouseEnter={() => setCardHover(true)}
        onMouseLeave={() => setCardHover(false)}
        onDragEnter={onDragEnter}
        onDragLeave={onDragLeave}
        onDragOver={onDragOver}
        onDrop={onDrop}
      >
        <AnimatePresence mode="wait">
          {showDropzone ? (
            <motion.div
              key="dropzone"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="px-6 py-10 sm:px-10 sm:py-12"
            >
              <div className="flex flex-col items-center text-center">
                <motion.div
                  className={`flex h-14 w-14 items-center justify-center rounded-2xl border border-white/[0.08] bg-lab-surface ${
                    phase === "dragging" ? "text-lab-accent" : "text-lab-muted"
                  }`}
                  animate={phase === "dragging" ? { scale: 1.06 } : { scale: 1 }}
                  transition={{ type: "spring", stiffness: 380, damping: 22 }}
                >
                  <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1.5}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                    />
                  </svg>
                </motion.div>

                <h3 className="mt-6 text-lg font-semibold text-lab-text sm:text-xl">
                  {phase === "selected" || phase === "uploading" ? "Your file" : "Drag and drop your report here"}
                </h3>
                <p className="mt-2 text-sm text-lab-muted sm:text-[15px]">
                  {phase === "uploading"
                    ? "Uploading securely…"
                    : phase === "selected"
                      ? "Preparing upload…"
                      : "Or upload a PDF from your device"}
                </p>

                {phase === "selected" || phase === "uploading" ? (
                  <motion.p
                    className="mt-3 max-w-full truncate px-2 text-xs text-lab-subtle sm:text-sm"
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    {fileName}
                  </motion.p>
                ) : null}

                {phase === "uploading" ? (
                  <div className="mt-6 h-1.5 w-full max-w-[240px] overflow-hidden rounded-full bg-lab-surface">
                    <motion.div
                      className="h-full rounded-full bg-lab-accent"
                      initial={{ width: "0%" }}
                      animate={{ width: `${progress}%` }}
                      transition={{ duration: 0.12, ease: "easeOut" }}
                    />
                  </div>
                ) : null}

                {error ? (
                  <p className="mt-4 text-sm text-red-400/90" role="alert">
                    {error}
                  </p>
                ) : null}

                <motion.div
                  className="mt-8"
                  whileHover={interactive && phase === "idle" ? { scale: 1.02 } : undefined}
                  whileTap={interactive && phase === "idle" ? { scale: 0.98 } : undefined}
                >
                  <input
                    ref={inputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    className="hidden"
                    onChange={onInputChange}
                  />
                  <button
                    type="button"
                    disabled={!interactive || phase === "selected"}
                    onClick={() => inputRef.current?.click()}
                    className="rounded-lg bg-lab-accent px-7 py-3 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/25 transition-shadow hover:shadow-lab-accent/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/50 disabled:pointer-events-none disabled:opacity-40"
                  >
                    Choose file
                  </button>
                </motion.div>

                <p className="mt-4 text-xs text-lab-subtle">PDF preferred</p>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="processing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              className="px-6 sm:px-10"
            >
              <UploadProgressState />
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </motion.div>
  );
}
