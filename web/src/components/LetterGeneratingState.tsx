import { motion } from "framer-motion";
import { lettersPurposeBlock } from "@/lib/intelligenceExpression";

/** Indeterminate activity — generation completion is server-driven, not this animation. */
export function LetterGeneratingState() {
  const purpose = lettersPurposeBlock();
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center px-2 pt-6 sm:pt-10">
      <p className="text-center text-[10px] font-semibold uppercase tracking-[0.18em] text-lab-accent">
        Your program · Letters
      </p>
      <div className="relative mt-4 h-1 w-full max-w-[240px] overflow-hidden rounded-full bg-white/[0.06]">
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
        Now we&apos;re generating your dispute letters
      </h2>
      <p className="mt-2 text-center text-sm leading-relaxed text-lab-muted">
        Creating bureau-ready dispute text from the plan you locked in — the same letter engine as
        the rest of your program. Nothing else required from you here.
      </p>
      <p className="mt-4 max-w-sm text-center text-xs leading-relaxed text-lab-subtle sm:text-sm">
        {purpose.paragraphs[0]}
      </p>
    </div>
  );
}
