import { motion } from "framer-motion";

/** Indeterminate activity — generation completion is server-driven, not this animation. */
export function LetterGeneratingState() {
  return (
    <motion.div
      className="mx-auto flex max-w-sm flex-col items-center px-2 pt-4 sm:pt-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="relative h-1 w-full max-w-[240px] overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className="absolute inset-y-0 w-1/3 rounded-full bg-lab-accent/85"
          initial={{ left: "-33%" }}
          animate={{ left: "100%" }}
          transition={{ duration: 1.35, repeat: Infinity, ease: "linear" }}
        />
      </div>
      <motion.div
        className="mt-8 h-2 w-2 rounded-full bg-lab-accent/80"
        animate={{ opacity: [0.35, 1, 0.35], scale: [0.92, 1, 0.92] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        aria-hidden
      />
      <h2 className="mt-6 text-center text-lg font-semibold tracking-tight text-lab-text sm:text-xl">
        Preparing your letters…
      </h2>
      <p className="mt-2 text-center text-sm leading-relaxed text-lab-muted">
        We&apos;re turning your confirmed round into draft documents now. This usually only takes a
        moment.
      </p>
      <p className="mt-4 max-w-sm text-center text-xs leading-relaxed text-lab-subtle sm:text-sm">
        Nothing is mailed from this step — you&apos;ll review each draft here first.
      </p>
    </motion.div>
  );
}
