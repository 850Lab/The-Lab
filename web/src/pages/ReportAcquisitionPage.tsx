import { motion } from "framer-motion";
import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { postCustomerUxEvent } from "@/lib/workflowApi";
import { ANNUAL_CREDIT_REPORT_URL } from "@/lib/reportAcquisitionConfig";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const UX_STEP = "upload";

const cardBase =
  "flex flex-col rounded-xl border border-white/[0.1] bg-lab-surface/95 p-5 text-left transition-colors hover:border-white/[0.14] sm:p-6";

export function ReportAcquisitionPage() {
  const navigate = useNavigate();
  const { token, workflowId } = useCustomerWorkflow();

  useEffect(() => {
    if (!token || !workflowId) return;
    void postCustomerUxEvent(token, workflowId, {
      event_name: "report_acquisition_page_viewed",
      step_id: UX_STEP,
      metadata: {},
    }).catch(() => {});
  }, [token, workflowId]);

  const fire = (event_name: string, extra: Record<string, unknown> = {}) => {
    if (token && workflowId) {
      void postCustomerUxEvent(token, workflowId, {
        event_name,
        step_id: UX_STEP,
        metadata: extra,
      }).catch(() => {});
    }
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[34%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-lg px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <p className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle">
          Before you upload
        </p>
        <h1 className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text">
          How would you like to get your credit report?
        </h1>
        <p className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted">
          Pick an option. You’ll upload a bureau PDF on the next screen when you’re ready.
        </p>

        <div className="mt-10 flex flex-col gap-4">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
          >
            <Link
              to="/get-report/idiq"
              className={`${cardBase} relative ring-1 ring-lab-accent/25`}
              onClick={() => fire("idiq_option_selected")}
            >
              <span className="mb-2 inline-flex w-fit rounded-md bg-lab-accent/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-sky-200">
                Recommended
              </span>
              <h2 className="text-[15px] font-semibold text-lab-text">
                Get your 3-bureau report
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                Use our recommended paid option to access a full 3-bureau credit report through
                IdentityIQ.
              </p>
              <span className="mt-4 text-sm font-semibold text-lab-accent">
                Continue to IdentityIQ →
              </span>
            </Link>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <a
              href={ANNUAL_CREDIT_REPORT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={cardBase}
              onClick={() => fire("free_report_option_selected")}
            >
              <h2 className="text-[15px] font-semibold text-lab-text">
                Use the free annual report option
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                You can also request a free report through AnnualCreditReport.com. Some users may
                receive only part of their bureau data depending on availability.
              </p>
              <span className="mt-4 text-sm font-semibold text-lab-accent">
                Go to AnnualCreditReport.com →
              </span>
            </a>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
          >
            <button
              type="button"
              className={`${cardBase} w-full cursor-pointer`}
              onClick={() => {
                fire("upload_existing_report_selected");
                navigate("/upload");
              }}
            >
              <h2 className="text-[15px] font-semibold text-lab-text">
                I already have my report
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                Upload your credit report PDF and continue your dispute workflow.
              </p>
              <span className="mt-4 text-sm font-semibold text-lab-accent">Upload my report →</span>
            </button>
          </motion.div>
        </div>

        <p className="mt-8 text-center text-xs text-lab-subtle">
          After you have a PDF, use Upload — then review, choose disputes, pay, generate letters, and
          mail when ready.
        </p>
      </main>
    </div>
  );
}
