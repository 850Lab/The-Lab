import { motion } from "framer-motion";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ContinueCTA } from "@/components/ContinueCTA";
import { FindingGroupCard, type FindingGroupCardProps } from "@/components/FindingGroupCard";
import { SummaryCard } from "@/components/SummaryCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { setWorkflowStep } from "@/lib/workflow";

const FINDINGS: FindingGroupCardProps[] = [
  {
    title: "Collections",
    count: 2,
    explanation: "These accounts were sent to collection and can weigh heavily on your score.",
    items: ["Medical Services — $428 reported", "Cellular Account — in collection since 2023"],
  },
  {
    title: "Charge-offs",
    count: 1,
    explanation: "A lender wrote this balance off; it often stays visible until addressed.",
    items: ["Retail Card — charged off, balance $1,240"],
  },
  {
    title: "Late payments",
    count: 4,
    explanation: "Recent late marks can signal risk to lenders and pull your score down.",
    items: [
      "Auto loan — 30 days late (March)",
      "Credit card — 30 days late (January)",
      "Store card — 30 days late (November)",
      "Installment loan — 30 days late (October)",
    ],
  },
];

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.06 },
  },
};

const headerBlock = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
  },
};

const groupsContainer = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.12, delayChildren: 0.04 },
  },
};

export function AnalysisPage() {
  const navigate = useNavigate();

  const totalCount = useMemo(
    () => FINDINGS.reduce((sum, g) => sum + g.count, 0),
    []
  );

  const handleContinue = () => {
    setWorkflowStep("prepare");
    navigate("/prepare", { replace: true });
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[28%] z-0 h-[min(60vw,420px)] w-[min(60vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.06] blur-[100px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-xl px-4 pb-16 pt-24 sm:px-6 sm:pb-20 sm:pt-28">
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          <motion.p
            variants={headerBlock}
            className="text-center text-xs font-medium uppercase tracking-[0.12em] text-lab-subtle"
          >
            Step 2 of 5
          </motion.p>

          <motion.h1
            variants={headerBlock}
            className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-3xl"
          >
            Here’s what we found
          </motion.h1>

          <motion.p
            variants={headerBlock}
            className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            We reviewed your report and identified items that may be affecting your credit.
          </motion.p>

          <motion.div variants={headerBlock} className="mt-8">
            <SummaryCard totalCount={totalCount} />
          </motion.div>

          <motion.div variants={groupsContainer} className="mt-6 space-y-4">
            {FINDINGS.map((group) => (
              <FindingGroupCard key={group.title} {...group} />
            ))}
          </motion.div>

          <motion.p
            variants={headerBlock}
            className="mt-8 text-center text-sm text-lab-muted"
          >
            We’ll guide you through fixing these next
          </motion.p>

          <motion.div variants={headerBlock} className="mt-8">
            <ContinueCTA onClick={handleContinue} />
          </motion.div>
        </motion.div>
      </main>
    </div>
  );
}
