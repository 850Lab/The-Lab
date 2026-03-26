import { motion } from "framer-motion";

export function LetterGeneratingState() {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center px-2 pt-6 sm:pt-10">
      <div className="relative h-1 w-full max-w-[220px] overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full bg-lab-accent/90"
          initial={{ width: "0%" }}
          animate={{ width: "100%" }}
          transition={{ duration: 2.1, ease: [0.45, 0, 0.55, 1] }}
        />
      </div>
      <motion.div
        className="mt-8 h-2 w-2 rounded-full bg-lab-accent/80"
        animate={{ opacity: [0.35, 1, 0.35], scale: [0.92, 1, 0.92] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
        aria-hidden
      />
      <h2 className="mt-6 text-center text-lg font-semibold tracking-tight text-lab-text sm:text-xl">
        Preparing your dispute letters…
      </h2>
      <p className="mt-2 text-center text-sm leading-relaxed text-lab-muted">
        We’re finalizing everything for you
      </p>
    </div>
  );
}
