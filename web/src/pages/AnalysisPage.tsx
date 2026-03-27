import { motion } from "framer-motion";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { FindingGroupCard } from "@/components/FindingGroupCard";
import { SummaryCard } from "@/components/SummaryCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { useIntakeSummary } from "@/hooks/useIntakeSummary";
import { buildFindingGroupsFromClaims } from "@/lib/reviewClaimsDisplay";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

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
  const { envelope, authoritativeStepId } = useCustomerWorkflow();
  const { bundle, loading, error } = useIntakeSummary();

  const parseRow = envelope?.stepStatus?.find((s) => s.stepId === "parse_analyze");
  const parseFailed = parseRow?.status === "failed";
  const parseInFlight =
    authoritativeStepId === "parse_analyze" &&
    parseRow &&
    parseRow.status !== "completed" &&
    parseRow.status !== "failed";

  const intake = bundle?.intake;
  const findingGroups = useMemo(
    () => (intake?.reviewClaims?.length ? buildFindingGroupsFromClaims(intake.reviewClaims) : []),
    [intake?.reviewClaims],
  );

  const totalClaims = intake?.reviewClaimsCount ?? 0;
  const reportRows = intake?.reports ?? [];

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
            Findings
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
            Summary from your uploaded bureau report (same analysis path as the main app). Next
            you’ll review line items, choose disputes, then pay for letter generation when you reach
            that step.
          </motion.p>

          {loading && !bundle ? (
            <motion.p variants={headerBlock} className="mt-10 text-center text-sm text-lab-muted">
              Loading your report summary…
            </motion.p>
          ) : null}

          {error ? (
            <motion.p
              variants={headerBlock}
              className="mt-10 text-center text-sm text-red-300/90"
            >
              {error}
            </motion.p>
          ) : null}

          {parseInFlight ? (
            <motion.p variants={headerBlock} className="mt-8 text-center text-sm text-lab-muted">
              Processing your report on our servers… this usually finishes in a few seconds. The
              page will update automatically.
            </motion.p>
          ) : null}

          {parseFailed ? (
            <motion.div variants={headerBlock} className="mt-8 space-y-4 text-center">
              <p className="text-sm text-lab-muted">
                We couldn’t finish analysis for this workflow step. You may need to upload again
                from the upload screen.
              </p>
              <Link
                to="/upload"
                className="inline-block text-sm font-medium text-lab-accent hover:text-lab-accent/90"
              >
                Back to upload
              </Link>
            </motion.div>
          ) : null}

          {!parseFailed && !parseInFlight && bundle ? (
            <>
              {reportRows.length > 0 ? (
                <motion.div variants={headerBlock} className="mt-8 space-y-3">
                  <p className="text-center text-xs font-medium uppercase tracking-[0.12em] text-lab-subtle">
                    Reports on file
                  </p>
                  <ul className="space-y-2 rounded-xl border border-white/[0.08] bg-lab-surface p-4 text-sm text-lab-text/90">
                    {reportRows.map((r) => (
                      <li
                        key={r.reportId}
                        className="flex flex-col gap-0.5 border-b border-white/[0.06] pb-3 last:border-0 last:pb-0 sm:flex-row sm:justify-between"
                      >
                        <span className="font-medium capitalize">{r.bureau}</span>
                        <span className="text-lab-muted">
                          {r.fileName || "Report"}
                          {r.uploadDate ? ` · ${r.uploadDate}` : ""}
                        </span>
                        <span className="text-xs text-lab-subtle sm:text-sm">
                          {r.counts.accounts} accts · {r.counts.negativeItems} negatives ·{" "}
                          {r.counts.hardInquiries} hard inq.
                        </span>
                      </li>
                    ))}
                  </ul>
                </motion.div>
              ) : (
                <motion.p variants={headerBlock} className="mt-8 text-center text-sm text-lab-muted">
                  No parsed reports are stored for your account yet. If you just uploaded, wait a
                  moment and refresh.
                </motion.p>
              )}

              <motion.div variants={headerBlock} className="mt-8">
                <SummaryCard totalCount={totalClaims} />
              </motion.div>

              {findingGroups.length > 0 ? (
                <motion.div variants={groupsContainer} className="mt-6 space-y-4">
                  {findingGroups.map((group) => (
                    <FindingGroupCard key={group.title} {...group} />
                  ))}
                </motion.div>
              ) : reportRows.length > 0 ? (
                <motion.p
                  variants={headerBlock}
                  className="mt-6 text-center text-sm text-lab-muted"
                >
                  Parsed data is saved, but no review items were produced from this report yet.
                </motion.p>
              ) : null}

              <motion.p
                variants={headerBlock}
                className="mt-8 text-center text-sm text-lab-muted"
              >
                Next, you’ll confirm which items we should focus on.
              </motion.p>
            </>
          ) : null}
        </motion.div>
      </main>
    </div>
  );
}
