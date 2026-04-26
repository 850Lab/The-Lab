import { motion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AnalysisResultsExperience } from "@/components/AnalysisResultsExperience";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { GuidedAnalysisView } from "@/components/GuidedAnalysisView";
import { ReviewPhaseProgressStrip, ReviewReassuranceBlock } from "@/components/ReviewStepContinuity";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { useIntakeSummary } from "@/hooks/useIntakeSummary";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import { buildFindingGroupsFromClaims } from "@/lib/reviewClaimsDisplay";
import { stepChildVariants as headerBlock, stepPageVariants as pageVariants } from "@/lib/motionStep";
import { FREE_VALUE_LINE } from "@/lib/flowMicrocopy";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";

type AnalyzeLocationState = {
  uploadedReportFileName?: string;
} | null;

const SLOW_ANALYSIS_MS = 120_000;

export function AnalysisPage() {
  const location = useLocation();
  const { envelope, authoritativeStepId, canonicalCustomerPath, orionViewModel, workflowId } =
    useCustomerWorkflow();
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

  const showLightFindings =
    !parseInFlight && !parseFailed && !!bundle && totalClaims > 0 && intake?.reviewClaims?.length;

  const showLightNoItems =
    !parseInFlight && !parseFailed && !!bundle && totalClaims === 0 && reportRows.length > 0;

  const lightShell = showLightFindings || showLightNoItems;

  return (
    <div
      className={`relative min-h-full ${lightShell ? "bg-neutral-100" : "bg-lab-bg"}`}
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      {!lightShell ? <StepPageAmbientBackground /> : null}

      <TopBarMinimal />

      <StepMainColumn
        className={`relative z-10 mx-auto max-w-2xl px-4 pb-16 sm:px-6 sm:pb-20 ${stepMainColumnTopClass(!!workflowId, "analysis")}`}
      >
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
              <motion.div variants={headerBlock} className="mx-auto max-w-md text-center">
                <p className="mt-0 text-sm leading-relaxed text-lab-muted">
                  We&apos;re organizing your report into a review list…
                </p>
                <ReviewPhaseProgressStrip phase="analyze" />
                <ReviewReassuranceBlock />
              </motion.div>
              <div className="mt-8">
                <GuidedAnalysisView
                  fileNameHint={fileNameHint}
                  primaryReport={primaryReport}
                  showSlowHint={showSlowAnalysisHint}
                />
              </div>
            </>
          ) : (
            <>
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
                  {showLightFindings && intake?.reviewClaims ? (
                    <motion.div variants={headerBlock} className="space-y-4">
                      <AnalysisResultsExperience
                        claims={intake.reviewClaims}
                        findingGroups={findingGroups}
                        authoritativeStepId={authoritativeStepId ?? undefined}
                        findingsContinueHref={findingsContinueHref}
                      />
                      <p className="mx-auto max-w-prose text-center text-xs leading-relaxed text-neutral-600 sm:text-sm">
                        {FREE_VALUE_LINE}
                      </p>
                    </motion.div>
                  ) : null}

                  {showLightNoItems ? (
                    <motion.div
                      variants={headerBlock}
                      className="rounded-2xl border border-neutral-200/90 bg-white px-6 py-10 text-center shadow-sm shadow-neutral-900/5"
                    >
                      <h2 className="mx-auto mt-0 max-w-md text-balance font-heading text-xl font-semibold text-neutral-950 sm:text-2xl">
                        Your report is saved
                      </h2>
                      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-neutral-600">
                        We didn&apos;t surface review items from this file yet. Nothing is mailed to the
                        bureaus from here.
                      </p>
                      <Link
                        to={findingsContinueHref}
                        className="mt-8 inline-flex w-full max-w-sm items-center justify-center rounded-xl bg-neutral-950 py-3.5 text-[15px] font-semibold text-white shadow-md shadow-neutral-900/20"
                      >
                        Continue in your program
                      </Link>
                    </motion.div>
                  ) : null}

                  {!showLightFindings && !showLightNoItems ? (
                    <motion.div variants={headerBlock} className="mt-10 space-y-4 text-center">
                      <ProgramFlowBridge className="mx-auto max-w-md">
                        We&apos;re still syncing your summary, or nothing was parsed yet.{" "}
                        <span className="font-medium text-lab-text">One next step:</span> continue in
                        your program — you pick up at the right screen automatically.
                      </ProgramFlowBridge>
                      <Link
                        to={findingsContinueHref}
                        className="btn-primary-step inline-flex w-full max-w-sm sm:w-auto sm:px-10"
                      >
                        Continue in your program
                      </Link>
                    </motion.div>
                  ) : null}
                </>
              ) : null}
            </>
          )}
        </motion.div>
      </StepMainColumn>
    </div>
  );
}
