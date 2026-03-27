import { motion } from "framer-motion";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { postCustomerUxEvent } from "@/lib/workflowApi";
import {
  IDIQ_AFFILIATE_URL,
  openExternalUrl,
} from "@/lib/reportAcquisitionConfig";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const UX_STEP = "upload";

export function ReportAcquisitionIdiqBridgePage() {
  const { token, workflowId } = useCustomerWorkflow();

  useEffect(() => {
    if (!token || !workflowId) return;
    void postCustomerUxEvent(token, workflowId, {
      event_name: "idiq_bridge_viewed",
      step_id: UX_STEP,
      metadata: {},
    }).catch(() => {});
  }, [token, workflowId]);

  const onContinue = () => {
    if (token && workflowId) {
      void postCustomerUxEvent(token, workflowId, {
        event_name: "idiq_redirect_clicked",
        step_id: UX_STEP,
        metadata: {},
      }).catch(() => {});
    }
    openExternalUrl(IDIQ_AFFILIATE_URL);
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[34%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-lg px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <div className="mb-6 text-center">
          <Link
            to="/get-report"
            className="text-sm font-medium text-lab-accent hover:text-sky-300"
          >
            ← Back to options
          </Link>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-white/[0.1] bg-lab-surface/95 px-5 py-6 sm:px-6"
        >
          <h1 className="text-xl font-semibold tracking-tight text-lab-text">
            Continue to IdentityIQ
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-lab-muted">
            You’ll open IdentityIQ in a new tab to access your credit report.
          </p>
          <p className="mt-4 text-sm font-medium text-lab-text">Once you download your report:</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-relaxed text-lab-muted">
            <li>Come back here</li>
            <li>Upload the PDF</li>
            <li>We’ll review it and build your next steps</li>
          </ol>

          <button
            type="button"
            onClick={onContinue}
            className="mt-8 w-full rounded-lg bg-lab-accent py-3 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/20"
          >
            Continue to IdentityIQ
          </button>

          <div className="mt-4 text-center">
            <Link
              to="/upload"
              className="text-sm font-medium text-lab-muted hover:text-lab-accent"
            >
              I already have my report
            </Link>
          </div>
        </motion.div>
      </main>
    </div>
  );
}
