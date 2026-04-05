import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import { FindingGroupCard } from "@/components/FindingGroupCard";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { GuidedAnalysisView } from "@/components/GuidedAnalysisView";
import { SummaryCard } from "@/components/SummaryCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { useIntakeSummary } from "@/hooks/useIntakeSummary";
import { buildFindingGroupsFromClaims } from "@/lib/reviewClaimsDisplay";

type AnalyzeLocationState = {
  uploadedReportFileName?: string;
} | null;

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

const SLOW_ANALYSIS_MS = 120_000;

export function AnalysisPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { envelope, authoritativeStepId, canonicalCustomerPath } = useCustomerWorkflow();
  const { bundle, loading, error } = useIntakeSummary();

  const locState = (location.state as AnalyzeLocationState) ?? null;
  const fileNameHint = locState?.uploadedReportFileName?.trim() || null;

  const parseRow = envelope?.stepStatus?.find((s) => s.stepId === "parse_analyze");
  const parseFailed = parseRow?.status === "failed";
  const parseInFlight =
    authoritativeStepId === "parse_analyze" &&
    !!parseRow &&
    parseRow.status !== "completed" &&
    parseRow.status !== "failed";

  const parseStartedAtRef = useRef<number | null>(null);
  const [showSlowAnalysisHint, setShowSlowAnalysisHint] = useState(false);

  useEffect(() => {
    if (parseInFlight) {
      if (parseStartedAtRef.current == null) parseStartedAtRef.current = Date.now();
    } else {
      parseStartedAtRef.current = null;
      setShowSlowAnalysisHint(false);
    }
  }, [parseInFlight]);

  useEffect(() => {
    if (!parseInFlight) return;
    const id = window.setInterval(() => {
      const t0 = parseStartedAtRef.current;
      if (t0 != null && Date.now() - t0 > SLOW_ANALYSIS_MS) setShowSlowAnalysisHint(true);
    }, 5000);
    return () => clearInterval(id);
  }, [parseInFlight]);

  const wasParsingRef = useRef(false);
  const [celebrateDone, setCelebrateDone] = useState(false);
  useEffect(() => {
    if (parseInFlight) {
      wasParsingRef.current = true;
      return;
    }
    if (parseFailed) {
      wasParsingRef.current = false;
      return;
    }
    if (wasParsingRef.current && bundle) {
      wasParsingRef.current = false;
      setCelebrateDone(true);
      const t = window.setTimeout(() => setCelebrateDone(false), 8000);
      return () => clearTimeout(t);
    }
  }, [parseInFlight, parseFailed, bundle]);

  const intake = bundle?.intake;
  const findingGroups = useMemo(
    () => (intake?.reviewClaims?.length ? buildFindingGroupsFromClaims(intake.reviewClaims) : []),
    [intake?.reviewClaims],
  );

  const totalClaims = intake?.reviewClaimsCount ?? 0;
  const reportRows = intake?.reports ?? [];
  const primaryReport = reportRows[0] ?? null;

  const findingsContinueHref =
    authoritativeStepId === "review_claims" ? "/prepare" : canonicalCustomerPath;

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[28%] z-0 h-[min(60vw,420px)] w-[min(60vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.06] blur-[100px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-xl px-4 pb-16 pt-24 sm:px-6 sm:pb-20 sm:pt-28">
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          {parseInFlight ? (
            <>
              {error ? (
                <motion.p
                  variants={headerBlock}
                  className="mb-8 rounded-xl border border-red-500/25 bg-red-500/10 px-4 py-3 text-center text-sm text-red-200/95"
                >
                  {error}
                </motion.p>
              ) : null}
              <GuidedAnalysisView
                fileNameHint={fileNameHint}
                primaryReport={primaryReport}
                showSlowHint={showSlowAnalysisHint}
              />
            </>
          ) : (
            <>
              <AnimatePresence>
                {celebrateDone ? (
                  <motion.div
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.35 }}
                    className="mb-8 rounded-xl border border-emerald-500/30 bg-emerald-500/[0.12] px-4 py-3 text-center"
                  >
                    <p className="text-sm font-medium text-emerald-100/95">Analysis complete</p>
                    <p className="mt-1 text-sm leading-relaxed text-lab-muted">
                      Here&apos;s what we found in your report — grouped below. Next you&apos;ll move
                      into review and strategy in the same program flow.
                    </p>
                  </motion.div>
                ) : null}
              </AnimatePresence>

              <motion.p
                variants={headerBlock}
                className="text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-accent"
              >
                Your program · Findings
              </motion.p>

              <motion.h1
                variants={headerBlock}
                className="mt-2 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-3xl"
              >
                Here&apos;s what we found in your report
              </motion.h1>

              <motion.p
                variants={headerBlock}
                className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
              >
                Meaningful items are grouped by type so you can see what matters — not a raw list of
                every line. The same system that read your file is guiding you toward what to do next.
              </motion.p>

              {!parseInFlight && !parseFailed && bundle ? (
                <motion.div variants={headerBlock} className="mx-auto mt-5 max-w-md">
                  <ProgramFlowBridge>
                    <span className="font-medium text-lab-text">Now that we&apos;ve analyzed your report,</span>{" "}
                    what follows is the next beat in the same program — not a new place. Scroll to
                    review, then use one continue control when you&apos;re ready for strategy.
                  </ProgramFlowBridge>
                </motion.div>
              ) : null}

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

              {parseFailed ? (
                <motion.div variants={headerBlock} className="mt-8 space-y-4 text-center">
                  <p className="text-sm text-lab-muted">
                    We couldn&apos;t finish analysis for this step. Try uploading again from the
                    upload screen — your program will pick up from there.
                  </p>
                  <Link
                    to="/upload"
                    className="inline-block text-sm font-medium text-lab-accent hover:text-lab-accent/90"
                  >
                    Back to upload
                  </Link>
                </motion.div>
              ) : null}

              {!parseFailed && bundle ? (
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
                      No parsed reports are stored for your account yet. If you just finished
                      analysis, wait a moment and refresh.
                    </motion.p>
                  )}

                  {totalClaims > 0 ? (
                    <motion.div variants={headerBlock} className="mt-8">
                      <SummaryCard totalCount={totalClaims} />
                    </motion.div>
                  ) : null}

                  {findingGroups.length > 0 ? (
                    <>
                      <motion.p
                        variants={headerBlock}
                        className="mt-8 text-center text-xs font-semibold uppercase tracking-wide text-lab-subtle"
                      >
                        By category
                      </motion.p>
                      <motion.div variants={groupsContainer} className="mt-4 space-y-4">
                        {findingGroups.map((group) => (
                          <FindingGroupCard key={group.title} {...group} />
                        ))}
                      </motion.div>
                    </>
                  ) : reportRows.length > 0 ? (
                    <motion.p
                      variants={headerBlock}
                      className="mt-6 text-center text-sm text-lab-muted"
                    >
                      Parsed data is saved, but no review items were produced from this report yet.
                    </motion.p>
                  ) : null}

                  {totalClaims > 0 || reportRows.length > 0 ? (
                    <motion.div
                      variants={headerBlock}
                      className="mt-10 rounded-2xl border border-lab-accent/25 bg-gradient-to-b from-lab-accent/[0.06] to-lab-surface/60 px-5 py-7 text-center sm:px-7"
                    >
                      <p className="text-sm font-medium text-lab-text">Next in your program</p>
                      <p className="mx-auto mt-2 max-w-sm text-sm leading-relaxed text-lab-muted">
                        {authoritativeStepId === "review_claims" ? (
                          <>
                            <span className="font-medium text-lab-text">
                              Upload every bureau you want included in this round,
                            </span>{" "}
                            then continue. You can add more PDFs first, or begin review when you&apos;re
                            ready — strategy comes after you confirm your list.
                          </>
                        ) : (
                          <>
                            <span className="font-medium text-lab-text">Now that we&apos;ve shown you what we found,</span>{" "}
                            next we&apos;ll determine the best way to handle these — a short review of your
                            list, then your{" "}
                            <strong className="font-medium text-lab-text">dispute strategy</strong> (what
                            to challenge this round). One path forward.
                          </>
                        )}
                      </p>
                      {authoritativeStepId === "review_claims" ? (
                        <div className="mx-auto mt-6 flex w-full max-w-sm flex-col items-stretch gap-3 sm:max-w-md">
                          <button
                            type="button"
                            onClick={() => navigate("/prepare")}
                            className="inline-flex w-full items-center justify-center rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/20 sm:px-10"
                          >
                            Begin review
                          </button>
                          <Link
                            to="/upload"
                            className="inline-flex w-full items-center justify-center rounded-xl border border-white/[0.14] bg-white/[0.04] py-3.5 text-[15px] font-semibold text-lab-text hover:bg-white/[0.07]"
                          >
                            Add another report
                          </Link>
                        </div>
                      ) : (
                        <Link
                          to={findingsContinueHref}
                          className="mt-6 inline-flex w-full max-w-sm items-center justify-center rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/20 sm:w-auto sm:px-10"
                        >
                          Go to your current step
                        </Link>
                      )}
                      {authoritativeStepId === "review_claims" ? (
                        <p className="mt-3 text-xs text-lab-subtle">
                          Begin review opens your working list (same findings, grouped for editing).
                          Strategy is the step after that.
                        </p>
                      ) : null}
                    </motion.div>
                  ) : (
                    <motion.div variants={headerBlock} className="mt-10 space-y-4 text-center">
                      <ProgramFlowBridge className="mx-auto max-w-md">
                        We&apos;re still syncing your summary, or nothing was parsed yet.{" "}
                        <span className="font-medium text-lab-text">One next step:</span> continue in
                        your program — you pick up at the right screen automatically.
                      </ProgramFlowBridge>
                      <Link
                        to={findingsContinueHref}
                        className="inline-flex w-full max-w-sm items-center justify-center rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/20 sm:w-auto sm:px-10"
                      >
                        {authoritativeStepId === "review_claims"
                          ? "Continue in your program"
                          : "Go to your current step"}
                      </Link>
                    </motion.div>
                  )}
                </>
              ) : null}
            </>
          )}
        </motion.div>
      </main>
    </div>
  );
}
