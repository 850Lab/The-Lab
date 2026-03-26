import { motion } from "framer-motion";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FallbackConfirmPanel } from "@/components/FallbackConfirmPanel";
import { GetReportPanel } from "@/components/GetReportPanel";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { UploadDropzoneCard } from "@/components/UploadDropzoneCard";
import { setWorkflowStep } from "@/lib/workflow";

const page = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.09, delayChildren: 0.08 },
  },
};

const block = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
  },
};

export function UploadStep() {
  const navigate = useNavigate();
  const [getReportOpen, setGetReportOpen] = useState(false);
  const [fallbackOpen, setFallbackOpen] = useState(false);

  const handleFallbackContinue = () => {
    setFallbackOpen(false);
    setWorkflowStep("analyze");
    navigate("/analyze", { replace: true });
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[32%] z-0 h-[min(70vw,520px)] w-[min(70vw,520px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.08] blur-[100px]"
        aria-hidden
      />

      <GetReportPanel open={getReportOpen} onClose={() => setGetReportOpen(false)} />
      <FallbackConfirmPanel
        open={fallbackOpen}
        onClose={() => setFallbackOpen(false)}
        onContinue={handleFallbackContinue}
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto flex min-h-full max-w-2xl flex-col px-4 pb-20 pt-24 sm:px-6 sm:pb-24 sm:pt-28">
        <motion.div
          className="flex flex-1 flex-col items-center"
          variants={page}
          initial="hidden"
          animate="show"
        >
          <motion.div variants={block} className="max-w-lg text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-lab-text sm:text-3xl md:text-[1.75rem]">
              Upload your credit report
            </h1>
            <p className="mt-3 text-pretty text-sm leading-relaxed text-lab-muted sm:text-base">
              We’ll review it, identify what may be hurting your credit, and guide you step by step.
            </p>
          </motion.div>

          <motion.div variants={block} className="mt-10 w-full sm:mt-12">
            <UploadDropzoneCard />
          </motion.div>

          <motion.div
            variants={block}
            className="mt-10 flex w-full max-w-lg flex-col items-center gap-3 sm:mt-12"
          >
            <motion.button
              type="button"
              onClick={() => setGetReportOpen(true)}
              className="text-center text-sm text-lab-subtle transition-colors hover:text-lab-muted"
              whileHover={{ y: -1 }}
              transition={{ type: "spring", stiffness: 400, damping: 28 }}
            >
              Don’t have your report?
            </motion.button>
            <motion.button
              type="button"
              onClick={() => setFallbackOpen(true)}
              className="text-center text-sm text-lab-subtle/90 transition-colors hover:text-lab-muted"
              whileHover={{ y: -1 }}
              transition={{ type: "spring", stiffness: 400, damping: 28 }}
            >
              Continue without a report
            </motion.button>
          </motion.div>
        </motion.div>
      </main>
    </div>
  );
}
