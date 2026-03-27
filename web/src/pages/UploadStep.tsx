import { motion } from "framer-motion";
import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GetReportPanel } from "@/components/GetReportPanel";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { UploadDropzoneCard } from "@/components/UploadDropzoneCard";
import { postReportUpload } from "@/lib/workflowApi";
import { customerPathFromEnvelope } from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

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

function skipReasonMessage(reason: string): string {
  switch (reason) {
    case "no_text":
      return "We could not read text from this PDF. Try another export or a clearer scan.";
    case "unknown":
      return "We could not confirm this is an Equifax, Experian, or TransUnion report.";
    case "3bureau":
      return "Combined 3-bureau PDFs are not supported. Upload one bureau at a time.";
    default:
      return `This file could not be processed (${reason}).`;
  }
}

export function UploadStep() {
  const navigate = useNavigate();
  const [getReportOpen, setGetReportOpen] = useState(false);
  const [privacyAgreed, setPrivacyAgreed] = useState(false);
  const { token, workflowId, applyWorkflowEnvelope } = useCustomerWorkflow();

  const onUploadPdf = useCallback(
    async (file: File) => {
      if (!token || !workflowId) {
        return {
          success: false as const,
          message: "Session or workflow missing. Return home and start again.",
        };
      }
      try {
        const r = await postReportUpload(token, workflowId, file, privacyAgreed);
        applyWorkflowEnvelope(r.workflow);
        if (!r.ok) {
          const first = r.fileSkips[0];
          const msg = first
            ? skipReasonMessage(first.reason)
            : r.workflow.userMessage || "Upload could not be completed.";
          return { success: false as const, message: msg };
        }
        const nextPath = customerPathFromEnvelope(r.workflow);
        navigate(nextPath, { replace: true });
        return { success: true as const };
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        return { success: false as const, message: msg };
      }
    },
    [token, workflowId, privacyAgreed, applyWorkflowEnvelope, navigate],
  );

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[32%] z-0 h-[min(70vw,520px)] w-[min(70vw,520px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.08] blur-[100px]"
        aria-hidden
      />

      <GetReportPanel open={getReportOpen} onClose={() => setGetReportOpen(false)} />

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
              Next we parse the PDF and extract reviewable items. After that you choose what to
              dispute, then pay for letter credits if needed — certified mail is a later step.
            </p>
            <p className="mt-3 text-sm text-lab-muted">
              Have your report downloaded? Upload one bureau PDF to continue.
            </p>
            <p className="mt-1 text-xs text-lab-subtle">
              If you only received part of your bureau data, upload what you have.
            </p>
            <p className="mt-3 text-center text-sm">
              <Link
                to="/get-report"
                className="font-medium text-lab-accent hover:text-sky-300"
              >
                Need to get a report first?
              </Link>
            </p>
          </motion.div>

          <motion.label
            variants={block}
            className="mt-8 flex max-w-lg cursor-pointer items-start gap-3 text-left text-sm text-lab-muted"
          >
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 shrink-0 rounded border-white/20 bg-lab-surface text-lab-accent focus:ring-lab-accent/40"
              checked={privacyAgreed}
              onChange={(e) => setPrivacyAgreed(e.target.checked)}
            />
            <span>
              I agree to secure processing of my report data (same terms as the main 850 Lab
              upload experience).
            </span>
          </motion.label>

          <motion.div variants={block} className="mt-8 w-full sm:mt-10">
            <UploadDropzoneCard disabled={!privacyAgreed} onUploadPdf={onUploadPdf} />
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
            <p className="text-center text-xs text-lab-subtle/80">
              Continue without a report is not available in the web app yet — use a bureau PDF to
              proceed.
            </p>
          </motion.div>
        </motion.div>
      </main>
    </div>
  );
}
