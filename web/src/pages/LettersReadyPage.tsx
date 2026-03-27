import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LetterGeneratingState } from "@/components/LetterGeneratingState";
import { LetterGroupCard } from "@/components/LetterGroupCard";
import { LetterPreviewModal } from "@/components/LetterPreviewModal";
import { LettersActionSection } from "@/components/LettersActionSection";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type { LetterRow, LettersUiFlags } from "@/lib/letterTypes";
import {
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
      setLoadError(null);
      setPageLoading(false);
      return;
    }
    setPageLoading(true);
    setLoadError(null);
    try {
      const data = await fetchLettersContext(token, workflowId);
      applyWorkflowEnvelope(data.workflow);
      setLetters(data.letters);
      setLettersUi(data.lettersUi);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setLetters([]);
      setLettersUi(null);
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
      const again = await fetchLettersContext(token, workflowId);
      applyWorkflowEnvelope(again.workflow);
      setLetters(again.letters);
      setLettersUi(again.lettersUi);
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
            >
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
                className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
              >
                Ready
              </motion.p>
              <motion.h1
                variants={headerVariants}
                className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
              >
                Your dispute letters are generated
              </motion.h1>
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
              >
                Letter text is generated from your dispute selection and reports (same engine as the
                main app). “Generated” means ready to review and download — certified mail is a
                later step after proof.
              </motion.p>

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
                    earlier step, refresh or go back to the workflow home.
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
