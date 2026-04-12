import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { EscalationProgramSection } from "@/components/EscalationProgramSection";
import { EscalationCTASection } from "@/components/EscalationCTASection";
import { EscalationOptionCard } from "@/components/EscalationOptionCard";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { RecommendedActionCard } from "@/components/RecommendedActionCard";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type { EscalationLayerPayload } from "@/lib/escalationLayerTypes";
import {
  DEFAULT_ESCALATION_ID,
  ESCALATION_OPTIONS,
  getEscalationOption,
  type EscalationOptionId,
} from "@/lib/escalationOptions";
import { fetchEscalationLayer } from "@/lib/workflowApi";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  stepChildVariants as headerVariants,
  stepChildVariants as sublabelVariants,
  stepNestedStaggerVariants as stackVariants,
  stepPageVariants as pageVariants,
} from "@/lib/motionStep";

const QUICK_TO_ACTION: Record<EscalationOptionId, string> = {
  furnisher: "furnisher_dispute",
  reverify: "follow_up_letter",
  cfpb: "cfpb_complaint",
};

const OPTION_ORDERING_HINTS: Record<EscalationOptionId, string> = {
  furnisher: "Best when a clear bureau response is already in hand",
  reverify: "Use this when something about their review still doesn’t add up",
  cfpb: "Usually considered later, after ordinary follow-up",
};

/** Softer surfaces — avoid alarm styling for trigger rows */
function triggerSurfaceClass(_severity: string): string {
  return "border-white/[0.1] bg-lab-surface/85";
}

function EscalationProgressStrip({
  responseReviewed,
}: {
  responseReviewed: boolean;
}) {
  return (
    <motion.div
      variants={headerVariants}
      className="surface-where-fits mx-auto mt-6 max-w-2xl"
    >
      <p className="text-center text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
        Where this fits
      </p>
      <ol className="mt-3 flex flex-col gap-2 text-sm sm:mt-4 sm:flex-row sm:justify-center sm:gap-3 sm:text-[13px]">
        <li
          className={
            responseReviewed
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted"
          }
        >
          <span
            className={
              responseReviewed ? "font-semibold text-emerald-200/95" : "text-lab-subtle"
            }
          >
            1.
          </span>
          <span className="ml-1.5">Response reviewed</span>
        </li>
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text">
          <span className="text-lab-accent">2.</span>
          <span className="ml-1.5">Escalation options considered</span>
        </li>
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted">
          <span className="text-lab-subtle">3.</span>
          <span className="ml-1.5">Action taken if needed</span>
        </li>
      </ol>
    </motion.div>
  );
}

function EscalationRoundContinuityModule({ layer }: { layer: EscalationLayerPayload | null }) {
  const n = layer?.context.responsesRecordedAfterFirstMail ?? 0;
  const mailed = layer?.context.hasLiveMail ?? false;

  return (
    <div className="surface-round-continuity">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-lab-subtle">
        Your current round
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        This page builds on the round you already mailed. Escalation is for when ordinary tracking
        or follow-up isn&apos;t enough — it isn&apos;t the default first move.
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        {n > 0 ? (
          <>
            You&apos;ve logged {n} response{n === 1 ? "" : "s"} after mail — use that context to
            choose the path that fits what actually happened.
          </>
        ) : (
          <>
            If you haven&apos;t logged a meaningful reply yet,{" "}
            <Link className="font-medium text-lab-accent hover:text-zinc-100" to="/responses">
              Responses
            </Link>{" "}
            is still the right place to capture it before leaning on stronger steps.
          </>
        )}
      </p>
      {!mailed && layer ? (
        <p className="mt-2 text-xs text-amber-200/90">
          Mail status looks incomplete — confirm send and tracking before choosing escalation paths.
        </p>
      ) : null}
    </div>
  );
}

function WhenThisPageMatters() {
  return (
    <div className="space-y-5 rounded-xl border border-white/[0.08] bg-lab-surface/50 px-4 py-4 sm:px-5 sm:py-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-lab-subtle">
          When this page is useful
        </p>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-lab-muted">
          <li>You received a response that still leaves the issue unresolved</li>
          <li>Tracking has moved far enough that a stronger next step may be appropriate</li>
          <li>You need a clearer follow-up path for this mailed round</li>
        </ul>
      </div>
      <div className="border-t border-white/[0.06] pt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-lab-subtle">
          When you may want to keep waiting instead
        </p>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-lab-muted">
          <li>Delivery or review timelines are still in a normal range</li>
          <li>There isn&apos;t a meaningful update yet</li>
          <li>The round hasn&apos;t reached a real decision point</li>
        </ul>
      </div>
    </div>
  );
}

function CopyScriptButton({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  const onCopy = useCallback(async () => {
    if (!text.trim()) return;
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 2000);
    } catch {
      /* ignore */
    }
  }, [text]);
  if (!text.trim()) return null;
  return (
    <button
      type="button"
      onClick={() => void onCopy()}
      className="mt-3 rounded-lg border border-white/[0.12] px-3 py-2 text-xs font-semibold text-lab-accent hover:bg-white/[0.04]"
    >
      {done ? "Copied" : "Copy call script"}
    </button>
  );
}

export function EscalationPage() {
  const navigate = useNavigate();
  const { token, workflowId, applyWorkflowEnvelope, loading: ctxLoading } = useCustomerWorkflow();
  const [selectedId, setSelectedId] = useState<EscalationOptionId>(DEFAULT_ESCALATION_ID);
  const [layer, setLayer] = useState<EscalationLayerPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const selected = getEscalationOption(selectedId);

  const responsesAfterMail = layer?.context.responsesRecordedAfterFirstMail ?? 0;
  const responseReviewedStrip = responsesAfterMail > 0;
  const hasProgramGroups =
    !!(layer?.programEscalation?.groups && layer.programEscalation.groups.length > 0);
  const showEarlyGuidance =
    layer &&
    !loading &&
    responsesAfterMail === 0 &&
    layer.triggers.length === 0 &&
    layer.actions.length === 0 &&
    !hasProgramGroups;

  useEffect(() => {
    if (!token || !workflowId) {
      setLayer(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    void fetchEscalationLayer(token, workflowId)
      .then((r) => {
        setLayer(r.escalationLayer);
        applyWorkflowEnvelope(r.workflow);
      })
      .catch((e) => {
        setLoadError(e instanceof Error ? e.message : String(e));
        setLayer(null);
      })
      .finally(() => setLoading(false));
  }, [token, workflowId, applyWorkflowEnvelope]);

  const handleContinue = () => {
    const aid = QUICK_TO_ACTION[selectedId];
    navigate(`/escalation-action?action=${encodeURIComponent(aid)}`, { replace: false });
  };

  const secondaryNav = (
    <div className="flex flex-col items-center gap-2 sm:flex-row sm:justify-center sm:gap-6">
      <Link
        className="text-sm font-medium text-lab-accent hover:text-zinc-100"
        to="/tracking"
      >
        Return to Tracking
      </Link>
      <Link
        className="text-sm font-medium text-lab-accent hover:text-zinc-100"
        to="/responses"
      >
        View Responses
      </Link>
    </div>
  );

  return (
    <div className="relative min-h-full bg-lab-bg">
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn className="relative z-10 mx-auto max-w-xl px-4 pb-28 pt-24 sm:px-6 sm:pb-32 sm:pt-28">
        {!ctxLoading && (!token || !workflowId) ? (
          <p className="mt-10 text-center text-sm text-lab-muted">
            Sign in and open your program to load next-step options tied to your mail and responses.
          </p>
        ) : null}
        {ctxLoading || (token && workflowId) ? (
          <motion.div variants={pageVariants} initial="hidden" animate="show" className="pb-4">
            <motion.p
              variants={headerVariants}
              className="step-eyebrow"
            >
              STEP 10 • REVIEW NEXT-STEP OPTIONS
            </motion.p>
            <motion.h1
              variants={headerVariants}
              className="step-title"
            >
              Review escalation paths for this round
            </motion.h1>
            <motion.p
              variants={headerVariants}
              className="step-support max-w-md"
            >
              Use this page when normal tracking or response handling is no longer enough for the
              round you already mailed. These options help you decide what to do next, in a calmer
              and more structured way.
            </motion.p>

            <motion.div
              variants={headerVariants}
              className="surface-emerald-reassure mx-auto mt-6 max-w-md text-left"
            >
              <ul className="space-y-2 text-sm leading-relaxed text-lab-muted">
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
                  <span>Escalation is only used when this round needs more follow-up</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
                  <span>You may not need every option shown here</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
                  <span>You can return to Tracking or Responses anytime</span>
                </li>
              </ul>
            </motion.div>

            <EscalationProgressStrip responseReviewed={responseReviewedStrip} />

            <motion.div variants={headerVariants} className="mt-6 space-y-3">
              <EscalationRoundContinuityModule layer={loading ? null : layer} />
              <ProgramFlowBridge>
                You don&apos;t need to use every option — pick what matches what actually happened.
                Escalation should fit the round, not fill a checklist. Use the links at the bottom of
                this page anytime you want to return to Tracking or Responses for context.
              </ProgramFlowBridge>
            </motion.div>

            {loadError ? (
              <motion.p
                variants={headerVariants}
                className="mt-6 text-center text-sm text-amber-200/95"
              >
                {loadError}
              </motion.p>
            ) : null}

            {loading ? (
              <p className="mt-8 text-center text-sm text-lab-muted">
                Loading options for your round…
              </p>
            ) : null}

            {!loading && layer?.leverageHeadline ? (
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-6 max-w-md text-center text-sm italic leading-relaxed text-lab-subtle"
              >
                {layer.subcopy ? (
                  <>
                    <span className="font-medium not-italic text-lab-muted">
                      {layer.leverageHeadline}
                    </span>
                    <br />
                    <span className="mt-1 block text-lab-subtle">{layer.subcopy}</span>
                  </>
                ) : (
                  <span className="font-medium not-italic text-lab-muted">{layer.leverageHeadline}</span>
                )}
              </motion.p>
            ) : null}

            {showEarlyGuidance ? (
              <motion.div
                variants={headerVariants}
                className="mt-8 rounded-xl border border-white/[0.1] bg-lab-bg/60 px-4 py-4 text-sm leading-relaxed text-lab-muted sm:px-5"
              >
                <p className="font-medium text-lab-text">You may not need escalation yet.</p>
                <p className="mt-2">
                  Tracking and Responses are still the right place if this round hasn&apos;t reached
                  a decision point or there&apos;s no meaningful update. Come back here when a
                  stronger next step is actually needed.
                </p>
              </motion.div>
            ) : null}

            <motion.div variants={headerVariants} className="mt-8">
              <WhenThisPageMatters />
            </motion.div>

            {!loading &&
            layer?.programEscalation?.groups &&
            layer.programEscalation.groups.length > 0 &&
            token &&
            workflowId ? (
              <motion.div variants={stackVariants} initial="hidden" animate="show" className="mt-8">
                <EscalationProgramSection
                  program={layer.programEscalation}
                  token={token}
                  workflowId={workflowId}
                  applyWorkflowEnvelope={applyWorkflowEnvelope}
                />
              </motion.div>
            ) : null}

            {!loading && layer && layer.triggers.length > 0 ? (
              <motion.div variants={stackVariants} initial="hidden" animate="show" className="mt-8 space-y-3">
                <motion.p
                  variants={sublabelVariants}
                  className="text-xs font-medium uppercase tracking-wide text-lab-subtle"
                >
                  Signals for this round
                </motion.p>
                <p className="text-xs leading-relaxed text-lab-subtle">
                  Context from your program — use it to compare paths, not as a demand to act
                  immediately.
                </p>
                {layer.triggers.map((t) => (
                  <motion.div
                    key={`${t.id}-${t.label}`}
                    variants={sublabelVariants}
                    className={`rounded-xl border px-4 py-3.5 ${triggerSurfaceClass(t.severity)}`}
                  >
                    <p className="text-sm font-semibold text-lab-text">{t.label}</p>
                    <p className="mt-2 text-sm leading-relaxed text-lab-muted">{t.detailSafe}</p>
                  </motion.div>
                ))}
              </motion.div>
            ) : null}

            {!loading && layer && layer.actions.length > 0 ? (
              <motion.div variants={stackVariants} initial="hidden" animate="show" className="mt-10 space-y-6">
                <motion.p
                  variants={sublabelVariants}
                  className="text-xs font-medium uppercase tracking-wide text-lab-subtle"
                >
                  Step-by-step paths (more detail)
                </motion.p>
                <p className="text-xs leading-relaxed text-lab-subtle">
                  Same ideas as the short cards below — open one when you want the full checklist.
                </p>
                {layer.actions.map((a) => (
                  <motion.article
                    key={a.id}
                    variants={sublabelVariants}
                    className="rounded-xl border border-white/[0.1] bg-lab-surface/90 px-4 py-4 sm:px-5 sm:py-5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h2 className="text-base font-semibold text-lab-text">{a.title}</h2>
                      <Link
                        to={`/escalation-action?action=${encodeURIComponent(a.id)}`}
                        className="shrink-0 text-xs font-semibold text-lab-accent hover:text-zinc-100"
                      >
                        Open checklist →
                      </Link>
                    </div>
                    <p className="mt-1 text-sm text-lab-muted">{a.tagline}</p>
                    <p className="mt-3 text-sm leading-relaxed text-lab-text/95">{a.whyNow}</p>
                    <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed text-lab-muted">
                      {a.steps.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ol>
                    {a.callScript?.trim() ? (
                      <div className="mt-4 rounded-lg border border-white/[0.08] bg-lab-bg/80 px-3 py-3">
                        <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">
                          Call script
                        </p>
                        <p className="mt-2 text-sm leading-relaxed text-lab-muted">{a.callScript}</p>
                        <CopyScriptButton text={a.callScript} />
                      </div>
                    ) : null}
                    {a.links.length > 0 ? (
                      <ul className="mt-4 space-y-2">
                        {a.links.map((lnk) => (
                          <li key={lnk.url}>
                            <a
                              href={lnk.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-lab-accent hover:text-zinc-100"
                            >
                              {lnk.label} ↗
                            </a>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </motion.article>
                ))}
              </motion.div>
            ) : null}

            <motion.div
              variants={stackVariants}
              initial="hidden"
              animate="show"
              className="mt-10 flex flex-col gap-5 sm:mt-11 sm:gap-6"
            >
              <motion.p
                variants={sublabelVariants}
                className="text-xs font-medium uppercase tracking-wide text-lab-subtle"
              >
                Shorter summary of the same paths
              </motion.p>
              <RecommendedActionCard option={selected} />

              <motion.p
                variants={sublabelVariants}
                className="text-xs font-medium uppercase tracking-wide text-lab-subtle"
              >
                Compare paths
              </motion.p>
              <p className="-mt-2 text-sm leading-relaxed text-lab-muted">
                If you&apos;re unsure how paths differ, read the one-line hint under each title —
                then pick the closest match. Nothing here has to be perfect on the first try.
              </p>

              {ESCALATION_OPTIONS.map((opt) => (
                <EscalationOptionCard
                  key={opt.id}
                  option={opt}
                  selected={selectedId === opt.id}
                  onSelect={() => setSelectedId(opt.id)}
                  orderingHint={OPTION_ORDERING_HINTS[opt.id]}
                />
              ))}
            </motion.div>

            <p className="mt-6 text-center text-sm leading-relaxed text-lab-muted">
              This helps keep the round accurate as new information comes in — you can always adjust
              after you learn more.
            </p>

            <EscalationCTASection
              onContinue={handleContinue}
              afterButton={secondaryNav}
            />

            <p className="mt-8 text-center text-[11px] leading-relaxed text-lab-subtle">
              Educational steps only — not legal advice. You decide what fits your situation.
            </p>
          </motion.div>
        ) : null}
      </StepMainColumn>
    </div>
  );
}
