import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

const DEFAULT_STATUS_LINES = [
  "Reviewing what stands out…",
  "Checking what may need a closer look…",
  "Pulling together what matters for you…",
] as const;

type Props = {
  title?: string;
  subtitle?: string;
  /** Cycling status under the progress bar. */
  statusLines?: readonly string[];
  /** Tighter vertical padding for dense layouts (e.g. upload step). */
  compact?: boolean;
};

export function UploadProgressState({
  title = "Analyzing your report…",
  subtitle = "Almost there — we’re building your review.",
  statusLines = DEFAULT_STATUS_LINES,
  compact = false,
}: Props) {
  const [lineIdx, setLineIdx] = useState(0);

  useEffect(() => {
    if (statusLines.length <= 1) return;
    const id = window.setInterval(() => {
      setLineIdx((i) => (i + 1) % statusLines.length);
    }, 3200);
    return () => window.clearInterval(id);
  }, [statusLines.length]);

  return (
    <div
      className={`flex flex-col items-center justify-center ${compact ? "py-6 sm:py-8" : "py-10 sm:py-14"}`}
    >
      <motion.div
        className={`relative w-full max-w-[min(100%,280px)] ${compact ? "px-1" : "px-2"}`}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        <div
          className="relative h-[3px] w-full overflow-hidden rounded-full bg-white/[0.07] shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)]"
          role="progressbar"
          aria-valuetext={title}
          aria-busy="true"
        >
          <motion.div
            className="absolute top-0 h-full w-[36%] rounded-full bg-gradient-to-r from-neutral-500/40 via-white/50 to-neutral-400/35"
            initial={{ left: "-36%" }}
            animate={{ left: ["-36%", "100%"] }}
            transition={{
              duration: 2.35,
              repeat: Infinity,
              ease: [0.42, 0, 0.2, 1],
            }}
          />
        </div>
      </motion.div>

      <motion.p
        className={`text-center font-semibold text-lab-text ${compact ? "mt-5 text-base sm:mt-6 sm:text-lg" : "mt-7 text-lg sm:text-xl"}`}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08, duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
      >
        {title}
      </motion.p>

      <div
        className={`min-h-[1.25rem] text-center ${compact ? "mt-2 sm:min-h-[1.35rem]" : "mt-3"}`}
        aria-live="polite"
      >
        <AnimatePresence mode="wait">
          <motion.p
            key={lineIdx}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.42, ease: [0.22, 1, 0.36, 1] }}
            className={`font-medium text-lab-muted ${compact ? "text-xs sm:text-sm" : "text-sm"}`}
          >
            {statusLines[lineIdx]}
          </motion.p>
        </AnimatePresence>
      </div>

      <motion.p
        className={`max-w-sm text-center text-lab-muted/90 ${compact ? "mt-3 text-[11px] sm:text-xs" : "mt-4 text-xs sm:text-sm"}`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.22, duration: 0.4 }}
      >
        {subtitle}
      </motion.p>
    </div>
  );
}
