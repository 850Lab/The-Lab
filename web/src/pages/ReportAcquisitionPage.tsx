import { motion } from "framer-motion";
import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { postCustomerUxEvent } from "@/lib/workflowApi";
import { ANNUAL_CREDIT_REPORT_URL } from "@/lib/reportAcquisitionConfig";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const UX_STEP = "upload";

const cardPrimary =
  "flex flex-col rounded-xl border border-zinc-700/50 bg-gradient-to-b from-white/[0.04] to-lab-surface/95 p-5 text-left shadow-lg shadow-black/20 transition-colors hover:border-zinc-600/55 sm:p-6";

const cardSecondary =
  "flex flex-col rounded-xl border border-white/[0.08] bg-lab-surface/80 p-5 text-left transition-colors hover:border-white/[0.14] sm:p-6";

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
        className="pointer-events-none absolute left-1/2 top-[34%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/[0.045] blur-[110px]"
        aria-hidden
      />
      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-lg px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <p className="step-eyebrow">
          850 Lab · Get your report
        </p>
        <h1 className="mt-2 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]">
          Get your credit report
        </h1>
        <p className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted">
          This is what powers your analysis — the same guided flow you&apos;re already in, now with
          your real bureau file. Choose how you&apos;ll obtain your PDF; your{" "}
          <strong className="font-medium text-lab-text">next step</strong> after that is{" "}
          <strong className="font-medium text-lab-text">upload</strong>, where we parse the report
          and guide you forward.
        </p>

        <div className="mt-10 flex flex-col gap-4">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
          >
            <Link
              to="/get-report/idiq"
              className={cardPrimary}
              onClick={() => fire("idiq_option_selected")}
            >
              <span className="mb-2 inline-flex w-fit rounded-md bg-white/[0.08] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-300">
                Primary path
              </span>
              <h2 className="text-[15px] font-semibold text-lab-text">
                Get your 3-bureau report (recommended)
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                Continue through IdentityIQ for full 3-bureau access — then come back here for the
                next step: upload.
              </p>
              <span className="mt-4 text-sm font-semibold text-lab-accent">
                Continue to IdentityIQ →
              </span>
            </Link>
          </motion.div>

          <p className="text-center text-xs font-medium uppercase tracking-wide text-lab-subtle">
            Other ways to get your file
          </p>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <a
              href={ANNUAL_CREDIT_REPORT_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={cardSecondary}
              onClick={() => fire("free_report_option_selected")}
            >
              <h2 className="text-[15px] font-semibold text-lab-text">
                Free annual report (AnnualCreditReport.com)
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                Request a free report; availability varies by bureau. When you have a PDF, return for
                upload — same program path.
              </p>
              <span className="mt-4 text-sm font-semibold text-lab-accent">
                Open AnnualCreditReport.com →
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
              className={`${cardSecondary} w-full cursor-pointer`}
              onClick={() => {
                fire("upload_existing_report_selected");
                navigate("/upload");
              }}
            >
              <h2 className="text-[15px] font-semibold text-lab-text">I already have my PDF</h2>
              <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                Skip straight to upload — and we&apos;ll run analysis on your file.
              </p>
              <span className="mt-4 text-sm font-semibold text-lab-accent">
                Go to upload — next step →
              </span>
            </button>
          </motion.div>
        </div>

        <p className="mt-10 text-center text-sm leading-relaxed text-lab-muted">
          After your PDF is ready, you&apos;re not “navigating away” — you&apos;re moving forward to
          upload, where your program starts analyzing your report.
        </p>
      </main>
    </div>
  );
}
