import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";

const TEASE_LINES = [
  "Finding what to fix first…",
  "Choosing your dispute set…",
  "Drafting bureau-ready letters…",
] as const;

const GHOST_LABELS = ["Late payment", "Collection", "Charge-off"] as const;

/**
 * White marketing hero shell: subtle silver pulse + slow shimmer (no interaction required).
 */
export function LandingHeroCard({ children }: { children: ReactNode }) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-neutral-200/90 bg-white px-6 py-9 text-center shadow-[0_24px_80px_-32px_rgba(15,23,42,0.14)] sm:px-10 sm:py-11">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neutral-400/50 to-transparent"
        aria-hidden
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-2xl"
        animate={{
          boxShadow: [
            "inset 0 0 0 1px rgba(163,163,163,0)",
            "inset 0 0 0 1px rgba(190,190,190,0.2)",
            "inset 0 0 0 1px rgba(163,163,163,0)",
          ],
        }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="pointer-events-none absolute inset-0 overflow-hidden rounded-2xl" aria-hidden>
        <motion.div
          className="absolute -left-[45%] top-0 h-full w-[50%] -skew-x-12 bg-gradient-to-r from-transparent via-neutral-400/[0.14] to-transparent"
          initial={false}
          animate={{ x: ["-5%", "280%"] }}
          transition={{
            duration: 12,
            repeat: Infinity,
            ease: "linear",
            repeatDelay: 2.5,
          }}
        />
      </div>
      <div className="relative z-[1]">{children}</div>
    </div>
  );
}

/**
 * Blurred faux-output + cycling status — teases the demo without showing real data.
 * Occasional brief “almost sharp” blur pulse + slightly higher contrast for glanceability.
 */
export function LandingDemoTease() {
  const [lineIdx, setLineIdx] = useState(0);
  const [peekSharp, setPeekSharp] = useState(false);

  useEffect(() => {
    const id = window.setInterval(() => {
      setLineIdx((i) => (i + 1) % TEASE_LINES.length);
    }, 2600);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const pulse = () => {
      setPeekSharp(true);
      window.setTimeout(() => setPeekSharp(false), 420);
    };
    const first = window.setTimeout(pulse, 3200);
    const id = window.setInterval(pulse, 9200);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(id);
    };
  }, []);

  const blurMain = peekSharp ? "blur-[1.6px]" : "blur-[3.5px]";
  const blurSub = peekSharp ? "blur-[1px]" : "blur-[2.5px]";
  const blurGhost = peekSharp ? "blur-[1.8px]" : "blur-[3px]";

  return (
    <div
      className="mt-7 flex flex-col items-center gap-2.5 sm:mt-8"
      data-testid="landing-demo-tease"
    >
      <motion.div
        layout
        className="relative w-full max-w-[288px] overflow-hidden rounded-xl border border-neutral-400/70 bg-gradient-to-b from-neutral-200/55 to-white px-3.5 py-3.5 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.8),0_1px_0_0_rgba(0,0,0,0.06)] transition-[border-color,box-shadow] duration-300"
        animate={{
          boxShadow: peekSharp
            ? "inset 0 1px 0 0 rgba(255,255,255,0.85), 0 0 0 1px rgba(115,115,115,0.12), 0 4px 20px -8px rgba(0,0,0,0.08)"
            : "inset 0 1px 0 0 rgba(255,255,255,0.75), 0 1px 0 0 rgba(0,0,0,0.04)",
        }}
        transition={{ duration: 0.25 }}
      >
        <p
          className={`select-none text-center text-[13px] font-semibold tracking-tight text-neutral-950 transition-[filter] duration-200 ease-out ${blurMain}`}
          aria-hidden
        >
          7 items flagged for review
        </p>
        <div
          className={`mt-2 flex flex-wrap justify-center gap-1.5 ${blurGhost}`}
          aria-hidden
        >
          {GHOST_LABELS.map((label) => (
            <span
              key={label}
              className="rounded-md border border-neutral-300/50 bg-neutral-100/80 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-neutral-700"
            >
              {label}
            </span>
          ))}
        </div>
        <p
          className={`mt-2 select-none text-center text-[11px] font-medium text-neutral-600 transition-[filter] duration-200 ease-out ${blurSub}`}
          aria-hidden
        >
          Dispute letters · your next step
        </p>
      </motion.div>
      <p
        className="min-h-[1.25rem] text-center text-[11px] font-medium tracking-wide text-neutral-500"
        aria-live="polite"
      >
        <AnimatePresence mode="wait">
          <motion.span
            key={lineIdx}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -3 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="inline-block"
          >
            {TEASE_LINES[lineIdx]}
          </motion.span>
        </AnimatePresence>
      </p>
    </div>
  );
}
