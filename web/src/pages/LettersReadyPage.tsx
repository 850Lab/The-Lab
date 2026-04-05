import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LetterGeneratingState } from "@/components/LetterGeneratingState";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { LetterGroupCard } from "@/components/LetterGroupCard";
import { CreditCommandPlanSection } from "@/components/CreditCommandPlanSection";
import { LetterPreviewModal } from "@/components/LetterPreviewModal";
import { LettersActionSection } from "@/components/LettersActionSection";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type { CreditCommandPlanResponse, LetterRow, LettersUiFlags } from "@/lib/letterTypes";
import {
  fetchCreditCommandPlan,
  fetchLetterContent,
  fetchLettersBundleTxt,
  fetchLettersContext,
  fetchWorkflowResume,
  postLettersGenerate,
} from "@/lib/workflowApi";
import {
  customerPathFromEnvelope,
  isAuthoritativeStepBefore,
} from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import { lettersPurposeBlock, postLettersWhatHappensNext } from "@/lib/intelligenceExpression";

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
  const { token, workflowId, authoritativeStepId, envelope, applyWorkflowEnvelope } =
    useCustomerWorkflow();

  const lettersPurpose = useMemo(() => lettersPurposeBlock(), []);
  const lettersProgramNext = useMemo(() => postLettersWhatHappensNext(), []);

  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [letters, setLetters] = useState<LetterRow[]>([]);
  const [lettersUi, setLettersUi] = useState<LettersUiFlags | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [bundleBusy, setBundleBusy] = useState(false);
  const [previewLetter, setPreviewLetter] = useState<LetterRow | null>(null);
  const [previewBody, setPreviewBody] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [creditCommandPlanBundle, setCreditCommandPlanBundle] =
    useState<CreditCommandPlanResponse | null>(null);

  const autoGenStartedRef = useRef(false);
  const genInFlightRef = useRef(false);

  useEffect(() => {
    autoGenStartedRef.current = false;
    genInFlightRef.current = false;
  }, [workflowId]);

  const loadContext = useCallback(async () => {
    if (!token || !workflowId) {
      setLetters([]);
      setLettersUi(null);
      setCreditCommandPlanBundle(null);
      setLoadError(null);
      setPageLoading(false);
      return;
    }
    setPageLoading(true);
    setLoadError(null);
    try {
      const [data, planBundle] = await Promise.all([
        fetchLettersContext(token, workflowId),
        fetchCreditCommandPlan(token, workflowId).catch(() => null),
      ]);
      applyWorkflowEnvelope(data.workflow);
      setLetters(data.letters);
      setLettersUi(data.lettersUi);
      setCreditCommandPlanBundle(planBundle);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setLetters([]);
      setLettersUi(null);
      setCreditCommandPlanBundle(null);
    } finally {
      setPageLoading(false);
    }
  }, [token, workflowId, applyWorkflowEnvelope]);

  useEffect(() => {
    void loadContext();
  }, [loadContext]);

  useEffect(() => {
    if (pageLoading || loadError) return;
    if (!envelope) return;
    if (!authoritativeStepId) return;
    if (isAuthoritativeStepBefore(authoritativeStepId, "letter_generation")) {
      navigate(customerPathFromEnvelope(envelope), { replace: true });
    }
  }, [pageLoading, loadError, envelope, authoritativeStepId, navigate]);

  const runLetterGeneration = useCallback(async () => {
    if (!token || !workflowId || genInFlightRef.current) return;
    genInFlightRef.current = true;
    setGenerating(true);
    setGenError(null);
    try {
      const r = await postLettersGenerate(token, workflowId);
      applyWorkflowEnvelope(r.workflow);
      const [again, planAgain] = await Promise.all([
        fetchLettersContext(token, workflowId),
        fetchCreditCommandPlan(token, workflowId).catch(() => null),
      ]);
      applyWorkflowEnvelope(again.workflow);
      setLetters(again.letters);
      setLettersUi(again.lettersUi);
      setCreditCommandPlanBundle(planAgain);
    } catch (e) {
      setGenError(e instanceof Error ? e.message : String(e));
      autoGenStartedRef.current = false;
    } finally {
      genInFlightRef.current = false;
      setGenerating(false);
    }
  }, [token, workflowId, applyWorkflowEnvelope]);

  useEffect(() => {
    if (!token || !workflowId || pageLoading || loadError) return;
    if (!lettersUi) return;
    if (!lettersUi.onLetterGenerationStep) return;
    if (lettersUi.letterGenerationCompleted) return;
    if (letters.length > 0) return;
    if (genError) return;
    if (autoGenStartedRef.current) return;
    if (genInFlightRef.current) return;
    autoGenStartedRef.current = true;
    void runLetterGeneration();
  }, [
    token,
    workflowId,
    pageLoading,
    loadError,
    lettersUi,
    letters.length,
    genError,
    runLetterGeneration,
  ]);

  const handleRetryGenerate = () => {
    setGenError(null);
    autoGenStartedRef.current = true;
    void runLetterGeneration();
  };

  const openPreview = useCallback(
    async (letter: LetterRow) => {
      if (!token || !workflowId) return;
      setPreviewLetter(letter);
      setPreviewBody("");
      setPreviewLoading(true);
      try {
        const { letterText } = await fetchLetterContent(token, workflowId, letter.id);
        setPreviewBody(letterText);
      } catch (e) {
        setPreviewBody(e instanceof Error ? e.message : String(e));
      } finally {
        setPreviewLoading(false);
      }
    },
    [token, workflowId],
  );

  const handleContinue = async () => {
    if (!token || !workflowId) return;
    try {
      const env = await fetchWorkflowResume(token, workflowId);
      applyWorkflowEnvelope(env);
      navigate(customerPathFromEnvelope(env), { replace: true });
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDownloadBundle = async () => {
    if (!token || !workflowId || letters.length === 0) return;
    setBundleBusy(true);
    try {
      const text = await fetchLettersBundleTxt(token, workflowId);
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "850-lab-dispute-letters.txt";
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setBundleBusy(false);
    }
  };

  const awaitingGeneration =
    !!lettersUi?.onLetterGenerationStep &&
    !lettersUi.letterGenerationCompleted &&
    letters.length === 0 &&
    !genError;

  const showGenerating = generating || (awaitingGeneration && !pageLoading && !loadError);

  const canContinue =
    letters.length > 0 &&
    (authoritativeStepId !== "letter_generation" || !!lettersUi?.letterGenerationCompleted);

  const showReadyBlock =
    !pageLoading &&
    !loadError &&
    !showGenerating &&
    !(lettersUi?.onLetterGenerationStep && letters.length === 0 && genError);

  const showGenFailure =
    !pageLoading &&
    !loadError &&
    !!lettersUi?.onLetterGenerationStep &&
    !lettersUi.letterGenerationCompleted &&
    letters.length === 0 &&
    !!genError;

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
        {pageLoading ? (
          <p className="text-center text-sm text-lab-muted">Loading letters…</p>
        ) : null}

        {loadError ? (
          <p className="text-center text-sm text-red-300/90">{loadError}</p>
        ) : null}

        <AnimatePresence mode="wait">
          {showGenerating ? (
            <motion.div
              key="gen"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              className="space-y-5"
            >
              <ProgramFlowBridge className="mx-auto max-w-sm">
                <span className="font-medium text-lab-text">Now that your dispute plan is set for this round,</span>{" "}
                we&apos;re generating letters — the next beat in the same program, not a separate tool
                to hunt for.
              </ProgramFlowBridge>
              <LetterGeneratingState />
            </motion.div>
          ) : null}

          {showGenFailure ? (
            <motion.div
              key="fail"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mx-auto max-w-sm space-y-4 pt-4"
            >
              <p className="text-center text-sm text-red-300/90">{genError}</p>
              <button
                type="button"
                onClick={handleRetryGenerate}
                disabled={generating}
                className="w-full rounded-xl border border-white/[0.12] bg-white/[0.04] py-3 text-[15px] font-medium text-lab-text transition-colors hover:border-lab-accent/35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35 disabled:opacity-45"
              >
                Try again
              </button>
            </motion.div>
          ) : null}

          {showReadyBlock ? (
            <motion.div
              key="ready"
              variants={pageVariants}
              initial="hidden"
              animate="show"
              className="pb-4"
            >
              <motion.p
                variants={headerVariants}
                className="text-center text-[10px] font-semibold uppercase tracking-[0.16em] text-lab-accent"
              >
                Your program · Letters
              </motion.p>
              <motion.h1
                variants={headerVariants}
                className="mt-2 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
              >
                Your dispute letters are ready
              </motion.h1>
              <motion.div
                variants={headerVariants}
                className="mx-auto mt-5 max-w-sm rounded-xl border border-lab-accent/20 bg-lab-surface/80 px-4 py-4 text-left sm:px-5 sm:py-5"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-lab-accent">
                  {lettersPurpose.headline}
                </p>
                {lettersPurpose.paragraphs.map((para) => (
                  <p
                    key={para.slice(0, 48)}
                    className="mt-2 text-sm leading-relaxed text-lab-muted sm:text-[15px]"
                  >
                    {para}
                  </p>
                ))}
              </motion.div>
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-4 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
              >
                This is a real outcome: bureau-specific dispute letter text built from your report
                and the items you chose — not a generic form. Use them to challenge inaccurate
                reporting; certified mail and proof come in the next steps of the same program.
              </motion.p>
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
              >
                <span className="font-medium text-lab-text">Next:</span> open each letter to review,
                download if you want a copy, then continue to proof and send when you&apos;re ready.
              </motion.p>
              <motion.div
                variants={headerVariants}
                className="mx-auto mt-6 max-w-sm rounded-xl border border-white/[0.1] bg-lab-bg/60 px-4 py-4 sm:px-5 sm:py-5"
              >
                <p className="text-sm font-semibold text-lab-text">{lettersProgramNext.headline}</p>
                <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-lab-muted">
                  {lettersProgramNext.bullets.map((b) => (
                    <li key={b.slice(0, 40)}>{b}</li>
                  ))}
                </ul>
              </motion.div>

              <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-sm">
                <ProgramFlowBridge>
                  <span className="font-medium text-lab-text">Now we&apos;ve prepared your dispute letters</span>{" "}
                  in this program — they&apos;re real outputs from the plan you locked in. Two clear
                  actions below: continue the program, or download everything.
                </ProgramFlowBridge>
              </motion.div>

              {lettersUi && lettersUi.selectedReviewClaimCount > 0 ? (
                <motion.p
                  variants={headerVariants}
                  className="mx-auto mt-2 max-w-sm text-center text-xs text-lab-subtle"
                >
                  Selection: {lettersUi.selectedReviewClaimCount} item
                  {lettersUi.selectedReviewClaimCount === 1 ? "" : "s"}
                </motion.p>
              ) : null}

              <motion.div
                variants={listVariants}
                initial="hidden"
                animate="show"
                className="mt-10 flex flex-col gap-3 sm:mt-11 sm:gap-3.5"
              >
                {letters.length === 0 ? (
                  <motion.p
                    variants={headerVariants}
                    className="text-center text-sm text-lab-muted"
                  >
                    No letter files are on record for your account yet. If you just finished an
                    earlier step, refresh or go back to program home.
                  </motion.p>
                ) : (
                  letters.map((letter) => (
                    <LetterGroupCard
                      key={letter.id}
                      letter={letter}
                      onViewLetter={() => void openPreview(letter)}
                    />
                  ))
                )}
              </motion.div>

              {creditCommandPlanBundle ? (
                <motion.div variants={headerVariants} className="mt-2">
                  <CreditCommandPlanSection
                    variant="letters"
                    plan={creditCommandPlanBundle.creditCommandPlan}
                    unavailableReason={creditCommandPlanBundle.unavailableReason}
                  />
                </motion.div>
              ) : null}

              <motion.div variants={headerVariants}>
                <LettersActionSection
                  onContinue={handleContinue}
                  onDownloadBundle={() => void handleDownloadBundle()}
                  continueDisabled={!canContinue}
                  downloadDisabled={letters.length === 0}
                  bundleBusy={bundleBusy}
                />
              </motion.div>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </main>

      <LetterPreviewModal
        open={previewLetter !== null}
        onClose={() => setPreviewLetter(null)}
        bureau={previewLetter?.bureauDisplay || previewLetter?.bureau || ""}
        body={previewBody}
        loading={previewLoading}
      />
    </div>
  );
}
