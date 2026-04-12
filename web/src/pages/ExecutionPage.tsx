import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  OtherOutcomePanel,
  OutcomePicker,
  OutcomeSuccessFlash,
} from "@/components/execution";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type { ExecutionOutcomeOption, ExecutionState } from "@/lib/executionRuntimeTypes";
import type { OutcomeLoggingPhase } from "@/lib/executionOutcomeTypes";
import { stepChildVariants as headerBlock, stepPageVariants as pageVariants } from "@/lib/motionStep";
import {
  fetchExecutionState,
  startExecutionSession,
  submitExecutionOutcome,
} from "@/lib/workflowApi";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const SESSION_RUN_KEY_PREFIX = "850lab.executionRun.v1:";

const POST_SUCCESS_MS = 1750;

/** Client fallback if API returns a primary block but empty outcomeOptions (should be rare). */
const FALLBACK_OUTCOME_OPTIONS: ExecutionOutcomeOption[] = [
  { id: "completed_as_expected", label: "I finished this step as described", outcomeKey: "complete", defaultNotes: "" },
  { id: "could_not_complete", label: "I couldn’t complete it (blocked or unclear)", outcomeKey: "complete", defaultNotes: "intent:could_not_complete" },
  { id: "need_more_time", label: "I need more time — I’ll come back to this", outcomeKey: "complete", defaultNotes: "intent:need_more_time" },
  { id: "got_partial_response", label: "I got a partial or unclear response", outcomeKey: "complete", defaultNotes: "intent:partial_or_unclear" },
];

function sessionRunKey(workflowId: string): string {
  return `${SESSION_RUN_KEY_PREFIX}${workflowId}`;
}

function pickFallbackOutcomeKey(options: ExecutionOutcomeOption[]): string {
  const c = options.find((o) => o.outcomeKey === "complete");
  return c?.outcomeKey ?? options[0]?.outcomeKey ?? "complete";
}

function outcomeOptionsForState(state: ExecutionState | null): ExecutionOutcomeOption[] {
  if (!state?.primaryActiveBlock) return [];
  const raw = state.outcomeOptions ?? [];
  if (raw.length > 0) return raw;
  return FALLBACK_OUTCOME_OPTIONS;
}

async function bootstrapExecutionState(
  token: string,
  workflowId: string,
): Promise<ExecutionState> {
  const key = sessionRunKey(workflowId);
  const stored = typeof sessionStorage !== "undefined" ? sessionStorage.getItem(key) : null;
  if (stored?.trim()) {
    try {
      const st = await fetchExecutionState(token, { runId: stored.trim() });
      sessionStorage.setItem(key, st.runId);
      return st;
    } catch {
      sessionStorage.removeItem(key);
      const started = await startExecutionSession(token, workflowId);
      sessionStorage.setItem(key, started.runId);
      return await fetchExecutionState(token, { runId: started.runId });
    }
  }
  try {
    const st = await fetchExecutionState(token, { workflowId });
    sessionStorage.setItem(key, st.runId);
    return st;
  } catch {
    const started = await startExecutionSession(token, workflowId);
    sessionStorage.setItem(key, started.runId);
    return await fetchExecutionState(token, { runId: started.runId });
  }
}

export function ExecutionPage() {
  const { token, workflowId, loading: ctxLoading } = useCustomerWorkflow();

  const [executionState, setExecutionState] = useState<ExecutionState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [phase, setPhase] = useState<OutcomeLoggingPhase>("choose");
  const [selectedPredefinedId, setSelectedPredefinedId] = useState<string | null>(null);
  const [otherSelected, setOtherSelected] = useState(false);
  const [otherText, setOtherText] = useState("");
  const [notSure, setNotSure] = useState(false);
  const [submitHint, setSubmitHint] = useState<string | null>(null);

  const advanceTimerRef = useRef<ReturnType<typeof window.setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (advanceTimerRef.current != null) window.clearTimeout(advanceTimerRef.current);
    };
  }, []);

  const reloadState = useCallback(async () => {
    if (!token || !workflowId) return;
    const key = sessionRunKey(workflowId);
    const rid = sessionStorage.getItem(key);
    if (!rid?.trim()) return;
    const st = await fetchExecutionState(token, { runId: rid.trim() });
    setExecutionState(st);
  }, [token, workflowId]);

  useEffect(() => {
    if (ctxLoading) return;
    if (!token || !workflowId) {
      setLoading(false);
      setExecutionState(null);
      setLoadError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    bootstrapExecutionState(token, workflowId)
      .then((st) => {
        if (!cancelled) {
          setExecutionState(st);
          setLoadError(null);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setExecutionState(null);
          setLoadError(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, workflowId, ctxLoading]);

  const resetOutcomeState = useCallback(() => {
    setPhase("choose");
    setSelectedPredefinedId(null);
    setOtherSelected(false);
    setOtherText("");
    setNotSure(false);
    setSubmitHint(null);
  }, []);

  const handleSelectPredefined = useCallback((id: string) => {
    setSelectedPredefinedId(id);
    setOtherSelected(false);
    setOtherText("");
    setNotSure(false);
    setPhase("choose");
    setSubmitHint(null);
  }, []);

  const handleSelectOther = useCallback(() => {
    setSelectedPredefinedId(null);
    setOtherSelected(true);
    setOtherText("");
    setNotSure(false);
    setPhase("other_detail");
    setSubmitHint(null);
  }, []);

  const handleUseStandard = useCallback(() => {
    setOtherSelected(false);
    setOtherText("");
    setNotSure(false);
    setPhase("choose");
    setSubmitHint(null);
  }, []);

  const otherValid = otherText.trim().length >= 1 || notSure;
  const blocked = Boolean(executionState?.blockedReason);
  const interactionLocked = blocked || phase === "submitting" || phase === "acknowledged";

  const options = outcomeOptionsForState(executionState);
  const primary = executionState?.primaryActiveBlock ?? null;
  const activeBlockId = primary?.blockId ?? executionState?.activeBlockIds[0] ?? null;

  const finishSuccessSequence = useCallback(() => {
    setPhase("acknowledged");
    if (advanceTimerRef.current != null) window.clearTimeout(advanceTimerRef.current);
    advanceTimerRef.current = window.setTimeout(() => {
      advanceTimerRef.current = null;
      resetOutcomeState();
    }, POST_SUCCESS_MS);
  }, [resetOutcomeState]);

  const handleSubmitPredefined = useCallback(async () => {
    if (!token || !executionState?.runId || !activeBlockId || !selectedPredefinedId || otherSelected || phase !== "choose") return;
    const opt = options.find((o) => o.id === selectedPredefinedId);
    if (!opt) return;
    setPhase("submitting");
    setSubmitHint(null);
    try {
      const { progression } = await submitExecutionOutcome(token, executionState.runId, {
        blockId: activeBlockId,
        outcomeKey: opt.outcomeKey,
        notes: opt.defaultNotes ?? "",
        source: "user_reported",
      });
      await reloadState();
      resetOutcomeState();
      if (progression.accepted) {
        finishSuccessSequence();
      } else {
        setSubmitHint(
          progression.validationErrors?.length
            ? progression.validationErrors.join(" ")
            : "That didn’t apply. You can try a different option.",
        );
      }
    } catch {
      setPhase("choose");
      setSubmitHint("Something went wrong. Please try again.");
    }
  }, [
    token,
    executionState?.runId,
    activeBlockId,
    selectedPredefinedId,
    otherSelected,
    phase,
    options,
    reloadState,
    finishSuccessSequence,
    resetOutcomeState,
  ]);

  const handleSubmitOther = useCallback(async () => {
    if (!token || !executionState?.runId || !activeBlockId || phase !== "other_detail" || !otherValid) return;
    setPhase("submitting");
    setSubmitHint(null);
    const outcomeKey = pickFallbackOutcomeKey(options);
    try {
      const flags: Record<string, unknown> = {};
      if (notSure) flags.notSure = true;
      const { progression } = await submitExecutionOutcome(token, executionState.runId, {
        blockId: activeBlockId,
        outcomeKey,
        notes: otherText.trim(),
        externalFlags: flags,
        source: "user_reported",
      });
      await reloadState();
      resetOutcomeState();
      if (progression.accepted) {
        finishSuccessSequence();
      } else {
        setPhase("other_detail");
        setSubmitHint(
          progression.validationErrors?.length
            ? progression.validationErrors.join(" ")
            : "That didn’t apply. Adjust your note and try again.",
        );
      }
    } catch {
      setPhase("other_detail");
      setSubmitHint("Something went wrong. Please try again.");
    }
  }, [
    token,
    executionState?.runId,
    activeBlockId,
    phase,
    otherValid,
    otherText,
    notSure,
    options,
    reloadState,
    finishSuccessSequence,
    resetOutcomeState,
  ]);

  const showOutcomeUi = primary && activeBlockId && !blocked;
  const showIdleDone = !loading && !loadError && executionState && !blocked && !primary;

  return (
    <div className="relative min-h-full bg-lab-bg">
      <StepPageAmbientBackground />
      <TopBarMinimal />

      <StepMainColumn className="relative z-10 mx-auto max-w-xl px-4 pb-28 pt-24 sm:px-6 sm:pb-32 sm:pt-28">
        <motion.div variants={pageVariants} initial="hidden" animate="show" className="space-y-8">
          <motion.header variants={headerBlock} className="text-center">
            <p className="step-eyebrow">Guided execution</p>
            <h1 className="step-title">Your step</h1>
            <p className="step-support">
              One action at a time. When you&apos;re done, log what happened so your plan can adapt.
            </p>
          </motion.header>

          {!token || !workflowId ? (
            <motion.p variants={headerBlock} className="text-center text-sm text-lab-muted">
              Sign in with an active workflow to use guided execution.
            </motion.p>
          ) : null}

          {loadError ? (
            <motion.p variants={headerBlock} className="rounded-2xl border border-white/[0.1] bg-lab-surface/50 px-4 py-3 text-center text-sm text-lab-muted">
              {loadError}
            </motion.p>
          ) : null}

          {loading ? (
            <motion.p variants={headerBlock} className="text-center text-sm text-lab-muted">
              Loading your plan…
            </motion.p>
          ) : null}

          {blocked && executionState?.blockedReason ? (
            <motion.section
              variants={headerBlock}
              className="rounded-2xl border border-white/[0.1] bg-lab-surface/50 p-5 text-center sm:p-6"
            >
              <p className="text-sm font-medium text-lab-text">Plan needs a quick reset</p>
              <p className="mt-2 text-sm leading-relaxed text-lab-muted">
                {executionState.blockedReason.replace(/_/g, " ")}
              </p>
              <p className="mt-3 text-xs text-lab-subtle">
                Your progress is saved. Check back after updates or contact support if this persists.
              </p>
            </motion.section>
          ) : null}

          {showIdleDone ? (
            <motion.section
              variants={headerBlock}
              className="rounded-2xl border border-white/[0.1] bg-lab-surface/60 p-5 sm:p-6"
            >
              <h2 className="text-left text-lg font-semibold tracking-tight text-lab-text">You&apos;re caught up</h2>
              <p className="mt-3 text-left text-sm leading-relaxed text-lab-muted">
                There isn&apos;t an active step right now. When the next action is ready, it will appear here.
              </p>
            </motion.section>
          ) : null}

          {primary && !blocked ? (
            <motion.section
              variants={headerBlock}
              className="rounded-2xl border border-white/[0.1] bg-lab-surface/60 p-5 sm:p-6"
            >
              <h2 className="text-left text-lg font-semibold tracking-tight text-lab-text">{primary.actionName}</h2>
              <p className="mt-3 whitespace-pre-wrap text-left text-sm leading-relaxed text-lab-muted">
                {primary.instructions}
              </p>
              {primary.cautionNotes.length > 0 ? (
                <ul className="mt-4 list-disc space-y-1.5 pl-5 text-left text-xs leading-relaxed text-lab-subtle">
                  {primary.cautionNotes.map((n, i) => (
                    <li key={`${i}-${n.slice(0, 24)}`}>{n}</li>
                  ))}
                </ul>
              ) : null}
            </motion.section>
          ) : null}

          {submitHint ? (
            <motion.p variants={headerBlock} className="text-center text-xs text-lab-muted">
              {submitHint}
            </motion.p>
          ) : null}

          {showOutcomeUi && phase === "acknowledged" ? (
            <OutcomeSuccessFlash visible />
          ) : null}

          {showOutcomeUi && phase !== "acknowledged" ? (
            <>
              <motion.section variants={headerBlock}>
                <OutcomePicker
                  options={options.map(({ id, label }) => ({ id, label }))}
                  selectedPredefinedId={selectedPredefinedId}
                  otherSelected={otherSelected}
                  onSelectPredefined={handleSelectPredefined}
                  onSelectOther={handleSelectOther}
                  disabled={interactionLocked}
                />
              </motion.section>

              {selectedPredefinedId &&
              !otherSelected &&
              (phase === "choose" || phase === "submitting") ? (
                <motion.div variants={headerBlock} className="flex justify-center">
                  <button
                    type="button"
                    disabled={interactionLocked}
                    onClick={handleSubmitPredefined}
                    className="min-h-[48px] w-full max-w-sm rounded-xl bg-lab-accent px-6 py-3 text-center text-sm font-semibold text-lab-bg transition-opacity disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto sm:min-w-[240px]"
                  >
                    {phase === "submitting" ? "Saving…" : "Save & continue"}
                  </button>
                </motion.div>
              ) : null}

              {otherSelected && (phase === "other_detail" || phase === "submitting") ? (
                <motion.section variants={headerBlock}>
                  <OtherOutcomePanel
                    otherText={otherText}
                    notSure={notSure}
                    onOtherTextChange={setOtherText}
                    onNotSureChange={setNotSure}
                    onUseStandard={handleUseStandard}
                    onSubmit={handleSubmitOther}
                    canSubmit={otherValid}
                    submitting={phase === "submitting"}
                  />
                </motion.section>
              ) : null}
            </>
          ) : null}
        </motion.div>
      </StepMainColumn>
    </div>
  );
}
