import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { StrategyCTASection } from "@/components/StrategyCTASection";
import { StrategySectionCard } from "@/components/StrategySectionCard";
import { StrategySummaryCard } from "@/components/StrategySummaryCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { setWorkflowStep } from "@/lib/workflow";

const SECTIONS = [
  {
    title: "Start here",
    lines: [
      "We’ve prepared your disputes.",
      "We’re ready to move them into execution.",
      "This is the fastest way to begin addressing the items we found.",
    ],
  },
  {
    title: "What happens next",
    lines: [
      "Credit bureaus receive your disputes.",
      "They begin reviewing the items we challenged.",
      "You’ll be able to track progress inside your account.",
    ],
  },
  {
    title: "If more action is needed",
    lines: [
      "We’ll guide you through next steps if an item is verified.",
      "Additional escalation paths are available if needed.",
      "You won’t be left guessing what to do next.",
    ],
  },
] as const;

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.09, delayChildren: 0.05 },
  },
};

const headerVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

const sectionsContainerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.12, delayChildren: 0.06 },
  },
};

const sectionCardVariants = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
  },
};

export function StrategyPage() {
  const navigate = useNavigate();

  const handleStart = () => {
    setWorkflowStep("payment");
    navigate("/payment", { replace: true });
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[28%] z-0 h-[min(58vw,400px)] w-[min(58vw,400px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.07] blur-[96px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-xl px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          <motion.p
            variants={headerVariants}
            className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
          >
            Plan
          </motion.p>

          <motion.h1
            variants={headerVariants}
            className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-3xl"
          >
            Your 72-hour plan
          </motion.h1>

          <motion.p
            variants={headerVariants}
            className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            Here’s how we’ll help you start improving your credit right away.
          </motion.p>

          <motion.div variants={headerVariants} className="mt-8">
            <StrategySummaryCard themesText="collections, charge-offs, and late payments" />
          </motion.div>

          <motion.div
            variants={sectionsContainerVariants}
            className="mt-6 space-y-4 sm:mt-7 sm:space-y-5"
          >
            {SECTIONS.map((s) => (
              <StrategySectionCard
                key={s.title}
                title={s.title}
                lines={[...s.lines]}
                variants={sectionCardVariants}
              />
            ))}
          </motion.div>

          <motion.div variants={headerVariants} className="mt-10 sm:mt-12">
            <StrategyCTASection onStart={handleStart} />
          </motion.div>
        </motion.div>
      </main>
    </div>
  );
}
