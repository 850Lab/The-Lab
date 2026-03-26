import { motion } from "framer-motion";

export function SendingState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="mx-auto mt-10 w-full max-w-sm rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-7 shadow-lg shadow-black/20 sm:mt-11 sm:px-6 sm:py-8"
    >
      <div className="relative h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full bg-lab-accent/90"
          initial={{ width: "0%" }}
          animate={{ width: "100%" }}
          transition={{ duration: 2.35, ease: [0.45, 0, 0.55, 1] }}
        />
      </div>
      <motion.div
        className="mx-auto mt-8 h-1.5 w-1.5 rounded-full bg-lab-accent/75"
        animate={{ opacity: [0.35, 1, 0.35], scale: [0.9, 1, 0.9] }}
        transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
        aria-hidden
      />
      <h2 className="mt-6 text-center text-lg font-semibold tracking-tight text-lab-text sm:text-xl">
        Sending your disputes…
      </h2>
      <p className="mt-2 text-center text-sm leading-relaxed text-lab-muted">
        This usually only takes a moment
      </p>
    </motion.div>
  );
}
