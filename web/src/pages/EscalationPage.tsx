import { motion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { EscalationCTASection } from "@/components/EscalationCTASection";
import { EscalationOptionCard } from "@/components/EscalationOptionCard";
import { RecommendedActionCard } from "@/components/RecommendedActionCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import {
  DEFAULT_ESCALATION_ID,
  ESCALATION_OPTIONS,
  getEscalationOption,
  type EscalationOptionId,
} from "@/lib/escalationOptions";

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.04 },
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

const stackVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.09, delayChildren: 0.06 },
  },
};

const sublabelVariants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.36, ease: [0.22, 1, 0.36, 1] },
  },
};

export function EscalationPage() {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<EscalationOptionId>(
    DEFAULT_ESCALATION_ID,
  );

  const selected = getEscalationOption(selectedId);

  const handleContinue = () => {
    navigate("/escalation-action", { replace: true });
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[36%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[40%] z-0 h-[min(48vw,320px)] w-[min(48vw,320px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.04] blur-[90px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-28 pt-24 sm:px-6 sm:pb-32 sm:pt-28">
        <motion.div
          variants={pageVariants}
          initial="hidden"
          animate="show"
          className="pb-4"
        >
          <motion.p
            variants={headerVariants}
            className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
          >
            Next step
          </motion.p>
          <motion.h1
            variants={headerVariants}
            className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
          >
            Let’s take the next step
          </motion.h1>
          <motion.p
            variants={headerVariants}
            className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            If your disputes weren’t fully resolved, we’ll guide you through the
            best escalation path.
          </motion.p>

          <motion.div
            variants={stackVariants}
            initial="hidden"
            animate="show"
            className="mt-10 flex flex-col gap-5 sm:mt-11 sm:gap-6"
          >
            <RecommendedActionCard option={selected} />

            <motion.p
              variants={sublabelVariants}
              className="text-xs font-medium uppercase tracking-wide text-lab-subtle"
            >
              Escalation options
            </motion.p>

            {ESCALATION_OPTIONS.map((opt) => (
              <EscalationOptionCard
                key={opt.id}
                option={opt}
                selected={selectedId === opt.id}
                onSelect={() => setSelectedId(opt.id)}
              />
            ))}
          </motion.div>

          <EscalationCTASection onContinue={handleContinue} />
        </motion.div>
      </main>
    </div>
  );
}
