import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LetterGeneratingState } from "@/components/LetterGeneratingState";
import { LetterGroupCard } from "@/components/LetterGroupCard";
import { LetterPreviewModal } from "@/components/LetterPreviewModal";
import { LettersActionSection } from "@/components/LettersActionSection";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import {
  LETTER_GROUPS,
  letterPreviewBody,
  type LetterGroupData,
} from "@/lib/mockLetterGroups";
import { setWorkflowStep } from "@/lib/workflow";

const GENERATE_MS = 2200;

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

const listVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.06 },
  },
};

export function LettersReadyPage() {
  const navigate = useNavigate();
  const [ready, setReady] = useState(false);
  const [previewGroup, setPreviewGroup] = useState<LetterGroupData | null>(
    null,
  );

  useEffect(() => {
    const t = window.setTimeout(() => setReady(true), GENERATE_MS);
    return () => window.clearTimeout(t);
  }, []);

  const handleSend = () => {
    setWorkflowStep("proof");
    navigate("/proof", { replace: true });
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[38%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[42%] z-0 h-[min(48vw,300px)] w-[min(48vw,300px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.04] blur-[90px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <AnimatePresence mode="wait">
          {!ready ? (
            <motion.div
              key="gen"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            >
              <LetterGeneratingState />
            </motion.div>
          ) : (
            <motion.div
              key="ready"
              variants={pageVariants}
              initial="hidden"
              animate="show"
              className="pb-4"
            >
              <motion.p
                variants={headerVariants}
                className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
              >
                Ready
              </motion.p>
              <motion.h1
                variants={headerVariants}
                className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
              >
                Your dispute letters are ready
              </motion.h1>
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
              >
                We’ve prepared everything and grouped it for the next step.
              </motion.p>

              <motion.div
                variants={listVariants}
                initial="hidden"
                animate="show"
                className="mt-10 flex flex-col gap-3 sm:mt-11 sm:gap-3.5"
              >
                {LETTER_GROUPS.map((group) => (
                  <LetterGroupCard
                    key={group.id}
                    group={group}
                    onViewLetter={() => setPreviewGroup(group)}
                  />
                ))}
              </motion.div>

              <motion.div variants={headerVariants}>
                <LettersActionSection onSend={handleSend} />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <LetterPreviewModal
        open={previewGroup !== null}
        onClose={() => setPreviewGroup(null)}
        bureau={previewGroup?.bureau ?? ""}
        body={
          previewGroup
            ? letterPreviewBody(
                previewGroup.bureau,
                previewGroup.disputeCount,
              )
            : ""
        }
      />
    </div>
  );
}
