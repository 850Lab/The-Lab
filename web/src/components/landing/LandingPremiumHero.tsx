import { motion } from "framer-motion";

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.06 },
  },
};

const item = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
  },
};

type Props = {
  /** Primary CTA — scroll to guided demo */
  onTryDemo: () => void;
  /** Secondary CTA — early access / report flow (modal) */
  onRunReport: () => void;
  waitlistHint?: boolean;
};

export function LandingPremiumHero({ onTryDemo, onRunReport, waitlistHint }: Props) {
  return (
    <motion.div
      className="relative mx-auto max-w-3xl px-4 text-center sm:px-6"
      variants={container}
      initial="hidden"
      animate="show"
    >
      <motion.div
        variants={item}
        className="flex flex-col items-center gap-2 sm:flex-row sm:justify-center sm:gap-3"
      >
        <span
          data-testid="home-hero-eyebrow"
          className="inline-flex items-center rounded-full border border-white/25 bg-white/10 px-3.5 py-1 text-[10px] font-bold uppercase tracking-[0.22em] text-white/90"
        >
          Limited access
        </span>
        <span className="text-[11px] font-medium tracking-wide text-neutral-300">
          Early users only · expanding gradually
        </span>
      </motion.div>
      {waitlistHint ? (
        <motion.p variants={item} className="mt-3 text-xs font-medium text-neutral-400">
          Take the tour below — full access opens in waves.
        </motion.p>
      ) : null}

      <motion.h1
        variants={item}
        data-testid="home-hero-headline"
        className="mt-6 font-heading text-balance text-[1.85rem] font-semibold leading-[1.08] tracking-[-0.03em] text-white sm:mt-8 sm:text-[2.5rem] md:text-[2.75rem]"
      >
        Your credit report is telling a story. We show you what matters.
      </motion.h1>

      <motion.p
        variants={item}
        className="mx-auto mt-5 max-w-xl text-pretty text-sm font-medium leading-relaxed text-neutral-200 sm:text-[15px]"
      >
        See what&apos;s inconsistent, what changes the strategy, and what can be turned into action.
      </motion.p>

      <motion.div
        variants={item}
        className="mt-8 flex flex-col items-stretch justify-center gap-3 sm:mt-10 sm:flex-row sm:items-center"
      >
        <motion.button
          type="button"
          onClick={onTryDemo}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="rounded-[10px] bg-white px-8 py-3.5 text-[15px] font-semibold text-lab-bg shadow-[0_1px_0_0_rgba(255,255,255,0.35)_inset,0_12px_40px_-12px_rgba(255,255,255,0.35)] ring-2 ring-white/30 transition-shadow hover:shadow-[0_16px_48px_-12px_rgba(255,255,255,0.4)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 focus-visible:ring-offset-2 focus-visible:ring-offset-lab-bg"
        >
          Try the Demo
        </motion.button>
        <motion.button
          type="button"
          onClick={onRunReport}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="rounded-[10px] border-2 border-white/35 bg-white/[0.08] px-8 py-3.5 text-[15px] font-semibold text-white backdrop-blur-sm transition-colors hover:border-white/50 hover:bg-white/[0.14] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400/80 focus-visible:ring-offset-2 focus-visible:ring-offset-lab-bg"
        >
          Run Your Report
        </motion.button>
      </motion.div>
    </motion.div>
  );
}
