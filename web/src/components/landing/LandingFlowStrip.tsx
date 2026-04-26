import { motion } from "framer-motion";

const steps = ["Find", "Understand", "Dispute", "Track"] as const;

/**
 * One-line program journey — replaces a heavy multi-card “pillars” block for app-mode landing.
 */
export function LandingFlowStrip() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-20px" }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="mx-auto mt-10 flex max-w-2xl flex-wrap items-center justify-center gap-x-2 gap-y-2 px-4 text-center sm:mt-12"
      aria-label="How 850 Lab works in four moves"
    >
      {steps.map((s, i) => (
        <span key={s} className="inline-flex items-center gap-2 text-sm font-semibold text-neutral-200">
          {i > 0 ? <span className="text-neutral-500" aria-hidden>→</span> : null}
          <span className="rounded-full border border-white/15 bg-white/[0.06] px-3 py-1.5 text-white">
            {s}
          </span>
        </span>
      ))}
    </motion.div>
  );
}
