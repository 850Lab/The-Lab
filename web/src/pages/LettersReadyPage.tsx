import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LetterGeneratingState } from "@/components/LetterGeneratingState";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { LetterGroupCard } from "@/components/LetterGroupCard";
import { CreditCommandPlanSection } from "@/components/CreditCommandPlanSection";
import { LetterPreviewModal } from "@/components/LetterPreviewModal";
import { LettersActionSection } from "@/components/LettersActionSection";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { PresentationDetails } from "@/components/presentation/PresentationStepFrame";
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
import {
  FREE_VALUE_LINE,
  POST_DOWNLOAD_NEXT_STEPS,
  POST_DOWNLOAD_UPGRADE_LINE,
} from "@/lib/flowMicrocopy";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import { lettersPurposeBlock, postLettersWhatHappensNext } from "@/lib/intelligenceExpression";
import {
  lettersContinuePrimaryButtonClass,
  orionNarrativeCoherent,
  orionStepHeroCopy,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import {
  easeStep,
  stepChildVariants as headerVariants,
  stepListGroupVariants as listVariants,
  stepPageVariants as pageVariants,
} from "@/lib/motionStep";

type LettersStripPhase = "generating" | "ready" | "failed";

function LettersProgressStrip({ phase }: { phase: LettersStripPhase }) {
  const step2Done = phase === "ready";
  const step3Next = phase === "ready";

  return (
    <motion.div
      variants={headerVariants}
      className="surface-where-fits mx-auto mt-6 max-w-2xl"
    >
      <p className="text-center text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
        What happens next
      </p>
      <ol className="mt-3 flex flex-col gap-2 text-sm sm:mt-4 sm:flex-row sm:justify-center sm:gap-3 sm:text-[13px]">
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted">
          <span className="font-semibold text-emerald-200/95">1.</span>
          <span className="ml-1.5">Payment completed</span>
        </li>
        <li
          className={
            step2Done
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text"
          }
        >
          <span className={step2Done ? "font-semibold text-emerald-200/95" : "text-lab-accent"}>
            2.
          </span>
          <span className="ml-1.5">Letters prepared</span>
        </li>
        <li
          className={
            step3Next
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted"
          }
        >
          <span className={step3Next ? "text-lab-accent" : "text-lab-subtle"}>3.</span>
          <span className="ml-1.5">Proof and mailing next</span>
        </li>
      </ol>
    </motion.div>
  );
}

function RoundContinuityModule({
  selectedCount,
  letterGroups,
  bureauCount,
  phase,
}: {
  selectedCount: number;
  letterGroups: number;
  bureauCount: number;
  phase: LettersStripPhase;
}) {
  const summary =
    phase === "ready" && letterGroups > 0
      ? `These ${letterGroups} letter group${letterGroups === 1 ? "" : "s"} cover ${bureauCount} bureau target${bureauCount === 1 ? "" : "s"} for the ${selectedCount} item${selectedCount === 1 ? "" : "s"} you confirmed in Strategy. This is the document stage for the round you already approved — review before proof and mailing.`
      : selectedCount > 0
        ? `These drafts reflect the ${selectedCount} item${selectedCount === 1 ? "" : "s"} you confirmed in Strategy. This is the document stage for the round you already approved — nothing is mailed from this screen.`
        : "These drafts come from the round you confirmed in Strategy. Review them here before proof and mailing — nothing is mailed from this screen.";

  return (
    <div className="surface-round-continuity">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-lab-subtle">Your current round</p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">{summary}</p>
    </div>
  );
}

export function LettersReadyPage() {
  const navigate = useNavigate();
  const {
    token,
    workflowId,
    authoritativeStepId,
    envelope,
    applyWorkflowEnvelope,
    orionViewModel,
    integrityHints,
  } = useCustomerWorkflow();

  const lettersPurpose = useMemo(() => lettersPurposeBlock(), []);
  const lettersProgramNext = useMemo(() => postLettersWhatHappensNext(), []);

  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [letters, setLetters] = useState<LetterRow[]>([]);
  const [lettersUi, setLettersUi] = useState<LettersUiFlags | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [bundleBusy, setBundleBusy] = useState(false);
  const [postDownloadOpen, setPostDownloadOpen] = useState(false);
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
      setPostDownloadOpen(true);
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

  const bureauCount = useMemo(
    () => new Set(letters.map((l) => (l.bureauDisplay || l.bureau).trim())).size,
    [letters],
  );

  const stripPhase: LettersStripPhase = showGenFailure
    ? "failed"
    : showReadyBlock
      ? "ready"
      : "generating";

  const pageHeadline = showGenFailure
    ? "Your letters were not completed yet"
    : showReadyBlock
      ? "Your dispute letters are ready to review"
      : "Your dispute letters are being prepared for this round";

  const supportText = showGenFailure
    ? "You can try again without losing your round. Your selections and payment stay in place."
    : showReadyBlock
      ? "These letters are based on the selections you confirmed earlier. Review what was generated here before moving into proof and mailing steps."
      : "We’re preparing draft letters from your confirmed round. You’ll review them here before proof and mailing — nothing is sent from this page.";

  const phaseHeroFallback = useMemo(
    () => ({ title: pageHeadline, subtitle: supportText }),
    [pageHeadline, supportText],
  );

  const orionAuthority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const lettersHero = useMemo(() => {
    if (showGenFailure) {
      return {
        title: phaseHeroFallback.title,
        subtitle: phaseHeroFallback.subtitle,
        ctaEmphasis: "standard" as const,
      };
    }
    return orionStepHeroCopy(orionAuthority, orionViewModel, phaseHeroFallback);
  }, [showGenFailure, orionAuthority, orionViewModel, phaseHeroFallback]);

  const lettersCoherent = useMemo(
    () => orionNarrativeCoherent(orionAuthority, orionViewModel),
    [orionAuthority, orionViewModel],
  );

  const lettersActionProps = useMemo(() => {
    if (!lettersCoherent) {
      return {
        freeValueLine: FREE_VALUE_LINE,
      };
    }
    if (lettersHero.ctaEmphasis === "muted") {
      return {
        headline: "No rush — drafts are on this page when you want them",
        supportText: "Preview or download, then continue; proof comes next in the same program.",
        freeValueLine: FREE_VALUE_LINE,
        helperText: "Mailing stays later — nothing goes out from this step.",
      };
    }
    return {
      headline: "Review on this page",
      supportText: "Preview or download drafts, then continue when you’re ready.",
      freeValueLine: FREE_VALUE_LINE,
      helperText: "Proof is next; mailing stays later in the program.",
    };
  }, [lettersCoherent, lettersHero.ctaEmphasis]);

  const showLettersShell =
    !pageLoading && !loadError && (showGenerating || showGenFailure || showReadyBlock);

  return (
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn
        className={`relative z-10 mx-auto max-w-xl px-4 pb-24 sm:px-6 sm:pb-28 ${stepMainColumnTopClass(!!workflowId)}`}
      >
        {pageLoading ? (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="text-center text-sm text-lab-muted"
          >
            Loading your letter workspace…
          </motion.p>
        ) : null}

        {loadError ? (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="text-center text-sm text-red-300/90"
          >
            {loadError}
          </motion.p>
        ) : null}

        {showLettersShell ? (
          <motion.div
            variants={pageVariants}
            initial="hidden"
            animate="show"
            className="pb-2"
          >
            <motion.h2
              variants={headerVariants}
              className="step-title"
            >
              {stripPhase === "ready" && letters.length > 0
                ? "Your letters are ready"
                : lettersHero.title}
            </motion.h2>
            <motion.p
              variants={headerVariants}
              className="step-support"
            >
              {stripPhase === "ready" && letters.length > 0
                ? "Download a pack or continue—proof is next; mailing comes later in your program."
                : lettersHero.subtitle}
            </motion.p>
            <PresentationDetails label="What this step covers" className="mx-auto mt-5 max-w-lg">
              <div className="surface-emerald-reassure -mx-1 border-0 bg-emerald-500/10 px-3 py-3 sm:px-4">
                <ul className="space-y-2 text-left text-sm leading-relaxed text-emerald-50/95 sm:text-[15px]">
                  <li className="flex gap-2">
                    <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                      •
                    </span>
                    <span>From your confirmed round in Strategy</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                      •
                    </span>
                    <span>Still preparation — not mailed from here</span>
                  </li>
                </ul>
              </div>
              <div className="mt-4">
                <LettersProgressStrip phase={stripPhase} />
              </div>
              <div className="mt-4">
                <RoundContinuityModule
                  selectedCount={lettersUi?.selectedReviewClaimCount ?? 0}
                  letterGroups={letters.length}
                  bureauCount={bureauCount}
                  phase={stripPhase}
                />
              </div>
            </PresentationDetails>
          </motion.div>
        ) : null}

        <AnimatePresence mode="wait">
          {showGenerating ? (
            <motion.div
              key="gen"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -3 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="space-y-5"
            >
              <ProgramFlowBridge className="mx-auto max-w-lg">
                {lettersCoherent ? (
                  <>
                    <span className="font-medium text-lab-text">Preparation in progress.</span>{" "}
                    Draft letters are generating from your confirmed round — this screen is still
                    before proof or mailing.
                  </>
                ) : (
                  <>
                    <span className="font-medium text-lab-text">Same program, next step:</span>{" "}
                    we&apos;re turning your confirmed round into draft documents — this usually only
                    takes a moment. Payment didn&apos;t mail anything; this screen is still preparation.
                  </>
                )}
              </ProgramFlowBridge>
              <LetterGeneratingState />
            </motion.div>
          ) : null}

          {showGenFailure ? (
            <motion.div
              key="fail"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -3 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto max-w-lg space-y-4 pt-2"
            >
              <p className="text-center text-sm text-red-300/90">{genError}</p>
              <p className="text-center text-xs text-lab-subtle">
                You can try again without losing your round — your selections stay saved.
              </p>
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
              <PresentationDetails label="Why these letters" className="mx-auto mt-6 max-w-lg">
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
              </PresentationDetails>

              {!lettersCoherent ? (
                <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-lg">
                  <details className="details-calm rounded-xl border border-white/[0.1] bg-lab-bg/60 px-4 py-3 sm:px-5 sm:py-4">
                    <summary className="cursor-pointer list-none text-center text-sm font-medium text-lab-muted [&::-webkit-details-marker]:hidden">
                      More about what happens next (optional)
                    </summary>
                    <p className="mt-3 text-sm font-semibold text-lab-text">{lettersProgramNext.headline}</p>
                    <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed text-lab-muted">
                      {lettersProgramNext.bullets.map((b) => (
                        <li key={b.slice(0, 40)}>{b}</li>
                      ))}
                    </ul>
                  </details>
                </motion.div>
              ) : null}

              <motion.p
                variants={headerVariants}
                className="mx-auto mt-5 max-w-md text-center text-sm text-lab-muted"
              >
                {lettersCoherent
                  ? "Preview or download below—mailing and tracking are later steps when you’re ready."
                  : "Preview each letter, then continue. Proof and mailing follow in your program."}
              </motion.p>

              <motion.div
                variants={listVariants}
                initial="hidden"
                animate="show"
                className="mt-8 flex flex-col gap-3 sm:mt-9 sm:gap-3.5"
              >
                {letters.length === 0 ? (
                  <motion.p
                    variants={headerVariants}
                    className="text-center text-sm text-lab-muted"
                  >
                    No letter files are on record yet. If you just finished an earlier step, refresh
                    or return to your program home.
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
                  continueButtonClassName={lettersContinuePrimaryButtonClass(lettersHero.ctaEmphasis)}
                  {...lettersActionProps}
                />
              </motion.div>

              {postDownloadOpen ? (
                <motion.div
                  variants={headerVariants}
                  className="mx-auto mt-6 max-w-lg rounded-xl border border-white/[0.1] bg-lab-bg/40 px-4 py-4 sm:px-5"
                >
                  <p className="text-center text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
                    What to do next
                  </p>
                  <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-lab-muted sm:text-[15px]">
                    {POST_DOWNLOAD_NEXT_STEPS.map((s) => (
                      <li key={s.slice(0, 24)}>{s}</li>
                    ))}
                  </ol>
                  <p className="mt-4 text-center text-xs leading-relaxed text-lab-subtle sm:text-sm">
                    {POST_DOWNLOAD_UPGRADE_LINE}
                  </p>
                </motion.div>
              ) : null}
            </motion.div>
          ) : null}
        </AnimatePresence>
      </StepMainColumn>

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
