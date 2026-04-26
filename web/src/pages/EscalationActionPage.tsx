import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type {
  EscalationLayerPayload,
  EscalationLeverageAction,
} from "@/lib/escalationLayerTypes";
import type { ProgramEscalationActionRow } from "@/lib/escalationProgramTypes";
import { fetchEscalationLayer } from "@/lib/workflowApi";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  easeStep,
  stepChildVariants as headerVariants,
  stepPageVariants as pageVariants,
  stepSoftRevealVariants,
} from "@/lib/motionStep";

function NavLinksRow({ className = "" }: { className?: string }) {
  return (
    <div
      className={`flex flex-col gap-2 text-center text-sm sm:flex-row sm:flex-wrap sm:justify-center sm:gap-x-6 sm:gap-y-1 ${className}`}
    >
      <Link className="link-step text-sm font-semibold" to="/escalation">
        Back to Escalation
      </Link>
      <Link className="link-step-muted text-sm" to="/tracking">
        Return to Tracking
      </Link>
      <Link className="link-step-muted text-sm" to="/responses">
        View Responses
      </Link>
    </div>
  );
}

function RoundContinuityModule({
  context,
}: {
  context: EscalationLayerPayload["context"] | null;
}) {
  const n = context?.responsesRecordedAfterFirstMail ?? 0;
  return (
    <div className="surface-round-continuity">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-lab-subtle">
        Your current round
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        This checklist applies to the round you already mailed. Use it when tracking and any
        responses you logged point toward stronger follow-up — not because you have to rush.
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        If a different escalation path fits better, you can go back and choose another option
        anytime.
      </p>
      {n > 0 ? (
        <p className="mt-2 text-xs text-lab-subtle">
          You&apos;ve logged {n} response{n === 1 ? "" : "s"} after mail in this program — lean on
          that context as you work the steps.
        </p>
      ) : null}
    </div>
  );
}

function WhenChecklistFits() {
  return (
    <div className="surface-where-fits space-y-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-lab-subtle">
          When this checklist fits best
        </p>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-lab-muted">
          <li>You already reviewed the broader escalation options</li>
          <li>This path matches what came back in the round</li>
          <li>You&apos;re ready for a more specific next step</li>
        </ul>
      </div>
      <div className="border-t border-white/[0.06] pt-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-lab-subtle">
          You may want a different path if
        </p>
        <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm leading-relaxed text-lab-muted">
          <li>The facts of the round don&apos;t match this checklist</li>
          <li>You&apos;re still waiting on a meaningful update</li>
          <li>Another escalation option fits better</li>
        </ul>
      </div>
    </div>
  );
}

function RecoveryState({
  variant,
}: {
  variant: "missing" | "invalid" | "empty";
}) {
  const copy =
    variant === "missing"
      ? {
          title: "Choose a next-step path",
          body: "Open Escalation first and pick the checklist that fits this round. You can also revisit Tracking or Responses for context before you continue.",
        }
      : variant === "invalid"
        ? {
            title: "This next-step path could not be loaded",
            body: "Return to Escalation to choose the path that fits this round. You can also go back to Tracking or Responses for context.",
          }
        : {
            title: "No details for this path yet",
            body: "Try another option from Escalation, or check back after your program updates. Tracking and Responses stay available.",
          };

  return (
    <motion.div
      variants={stepSoftRevealVariants}
      initial="hidden"
      animate="show"
      className="mt-8 space-y-6 rounded-xl border border-white/[0.1] bg-lab-surface/50 px-4 py-5 sm:px-6"
    >
      <div>
        <p className="text-sm font-semibold text-lab-text">{copy.title}</p>
        <p className="mt-2 text-sm leading-relaxed text-lab-muted">{copy.body}</p>
      </div>
      <NavLinksRow />
    </motion.div>
  );
}

export function EscalationActionPage() {
  const [searchParams] = useSearchParams();
  const rawAction = searchParams.get("action");
  const actionMissing = rawAction === null || rawAction.trim() === "";
  const actionId = actionMissing ? "" : rawAction.trim();

  const { token, workflowId, applyWorkflowEnvelope, loading: ctxLoading } = useCustomerWorkflow();
  const [action, setAction] = useState<EscalationLeverageAction | null>(null);
  const [programAction, setProgramAction] = useState<ProgramEscalationActionRow | null>(null);
  const [layerContext, setLayerContext] = useState<EscalationLayerPayload["context"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  /** True when URL had an action id but nothing matched the loaded layer */
  const [actionNotFound, setActionNotFound] = useState(false);

  useEffect(() => {
    if (!token || !workflowId) {
      setAction(null);
      setProgramAction(null);
      setLayerContext(null);
      setActionNotFound(false);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setActionNotFound(false);
    void fetchEscalationLayer(token, workflowId)
      .then((r) => {
        applyWorkflowEnvelope(r.workflow);
        setLayerContext(r.escalationLayer.context);

        if (actionMissing) {
          setAction(null);
          setProgramAction(null);
          setActionNotFound(false);
          return;
        }

        let pa: ProgramEscalationActionRow | null = null;
        const groups = r.escalationLayer.programEscalation?.groups;
        if (groups) {
          for (const g of groups) {
            const hit = g.actions.find((x) => x.id === actionId);
            if (hit) {
              pa = hit;
              break;
            }
          }
        }
        const found = r.escalationLayer.actions.find((a) => a.id === actionId);
        setProgramAction(pa);
        if (pa || found) {
          setAction(found ?? null);
          setActionNotFound(false);
        } else {
          setAction(null);
          setProgramAction(null);
          setActionNotFound(true);
        }
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setAction(null);
        setProgramAction(null);
        setLayerContext(null);
        setActionNotFound(false);
      })
      .finally(() => setLoading(false));
  }, [token, workflowId, actionId, actionMissing, applyWorkflowEnvelope]);

  const title = useMemo(
    () => programAction?.title ?? action?.title ?? "This checklist",
    [programAction, action],
  );

  const [copiedScript, setCopiedScript] = useState(false);
  const [copiedDraft, setCopiedDraft] = useState(false);

  const copyScript = useCallback(async () => {
    const t = action?.callScript?.trim();
    if (!t) return;
    try {
      await navigator.clipboard.writeText(t);
      setCopiedScript(true);
      setTimeout(() => setCopiedScript(false), 2000);
    } catch {
      /* ignore */
    }
  }, [action]);

  const copyDraft = useCallback(async (text: string) => {
    if (!text.trim()) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedDraft(true);
      setTimeout(() => setCopiedDraft(false), 2000);
    } catch {
      /* ignore */
    }
  }, []);

  const hasContent = !!(action || programAction);
  const showRecoveryMissing = !ctxLoading && (token && workflowId) && !loading && !error && actionMissing;
  const showRecoveryInvalid =
    !ctxLoading && (token && workflowId) && !loading && !error && !actionMissing && actionNotFound;
  const showRecoveryEmpty =
    !ctxLoading &&
    (token && workflowId) &&
    !loading &&
    !error &&
    !actionMissing &&
    !actionNotFound &&
    !hasContent;

  /** Long-form Step 10 framing — hide when action query is missing or path failed to resolve */
  const showFullHero =
    !actionMissing &&
    !showRecoveryInvalid &&
    !showRecoveryEmpty &&
    (loading || hasContent);

  return (
    <div className="relative min-h-full bg-lab-bg">
      <StepPageAmbientBackground />
      <TopBarMinimal />
      <StepMainColumn
        className={`relative z-10 mx-auto max-w-xl px-4 pb-24 sm:px-6 sm:pb-28 ${stepMainColumnTopClass(!!workflowId)}`}
      >
        {!ctxLoading && (!token || !workflowId) ? (
          <p className="mt-6 text-sm text-lab-muted">
            Sign in with your program open to load this checklist.
          </p>
        ) : null}

        {ctxLoading || (token && workflowId) ? (
          <motion.div variants={pageVariants} initial="hidden" animate="show" className="pb-4">
            {showFullHero ? (
              <>
                <motion.h2
                  variants={headerVariants}
                  className="step-title"
                >
                  Work through this escalation path for your current round
                </motion.h2>
                <motion.p
                  variants={headerVariants}
                  className="step-support max-w-md"
                >
                  This page gives you one structured path based on the escalation option you
                  selected. Use it when this round needs stronger follow-up beyond normal tracking or
                  response handling.
                </motion.p>

                <motion.div
                  variants={headerVariants}
                  className="surface-emerald-reassure mx-auto mt-6 max-w-md text-left"
                >
                  <ul className="space-y-2 text-sm leading-relaxed text-lab-muted">
                    <li className="flex gap-2">
                      <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
                      <span>This is one option, not the only possible path</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
                      <span>You can return to Escalation, Tracking, or Responses anytime</span>
                    </li>
                    <li className="flex gap-2">
                      <span className="mt-0.5 shrink-0 text-emerald-300/95">✓</span>
                      <span>Move through this checklist at a steady pace</span>
                    </li>
                  </ul>
                </motion.div>

                <motion.p
                  variants={headerVariants}
                  className="mt-5 text-center text-xs leading-relaxed text-lab-subtle"
                >
                  <span className="text-lab-muted">Escalation</span>
                  <span className="mx-1.5 text-lab-subtle">→</span>
                  <span className="font-medium text-lab-text">{title}</span>
                </motion.p>

                <motion.div variants={headerVariants} className="mt-4">
                  <NavLinksRow />
                </motion.div>

                <motion.div variants={headerVariants} className="mt-6 space-y-3">
                  <RoundContinuityModule context={layerContext} />
                  <ProgramFlowBridge>
                    This checklist is here to keep the next step organized — not to pressure you
                    into a perfect run. Focus on the parts that fit what happened in your round; you
                    don&apos;t need to complete everything at once.
                  </ProgramFlowBridge>
                </motion.div>

                <motion.div variants={headerVariants} className="mt-6">
                  <WhenChecklistFits />
                </motion.div>
              </>
            ) : (
              <>
                <motion.h2
                  variants={headerVariants}
                  className="step-title mt-3 text-center"
                >
                  Next-step checklist
                </motion.h2>
                <motion.div variants={headerVariants} className="mt-6">
                  <RoundContinuityModule context={layerContext} />
                </motion.div>
              </>
            )}

            {loading ? (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, ease: easeStep }}
                className="mt-8 text-center text-sm text-lab-muted"
              >
                Loading checklist…
              </motion.p>
            ) : error ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, ease: easeStep }}
                className="mt-8 space-y-4 rounded-xl border border-white/[0.1] bg-lab-surface/50 px-4 py-5"
              >
                <p className="text-sm text-amber-200/95">{error}</p>
                <NavLinksRow />
              </motion.div>
            ) : showRecoveryMissing ? (
              <RecoveryState variant="missing" />
            ) : showRecoveryInvalid ? (
              <RecoveryState variant="invalid" />
            ) : showRecoveryEmpty ? (
              <RecoveryState variant="empty" />
            ) : hasContent ? (
              <div className="mt-8 space-y-6">
                <p className="text-sm leading-relaxed text-lab-muted">
                  {programAction?.summarySafe ?? action?.tagline ?? action?.whyNow ?? ""}
                </p>
                {action?.whyNow &&
                (!programAction?.summarySafe || action.whyNow !== programAction.summarySafe) ? (
                  <p className="text-sm leading-relaxed text-lab-text">{action.whyNow}</p>
                ) : null}

                <p className="text-xs leading-relaxed text-lab-subtle">
                  This checklist is here to keep the next step organized. You don&apos;t need to
                  complete everything instantly. If this path no longer fits, return to Escalation
                  and choose another one.
                </p>

                {programAction?.affectedItems && programAction.affectedItems.length > 0 ? (
                  <div className="rounded-xl border border-white/[0.08] bg-lab-surface/60 px-4 py-4">
                    <h2 className="text-sm font-semibold text-lab-text">Items this step refers to</h2>
                    <p className="mt-1 text-xs text-lab-subtle">
                      Quick reference from your round — not a verdict on what you must do.
                    </p>
                    <ul className="mt-3 space-y-2 text-sm text-lab-muted">
                      {programAction.affectedItems.map((it) => (
                        <li key={it.reviewClaimId} className="leading-relaxed">
                          <span className="font-mono text-xs text-lab-subtle">{it.reviewClaimId}</span>{" "}
                          — {it.line}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {programAction?.documentDraft?.trim() ? (
                  <details className="details-calm group rounded-xl border border-white/[0.1] bg-lab-surface/90 px-4 py-3 open:pb-4">
                    <summary className="cursor-pointer list-none text-sm font-semibold text-lab-text [&::-webkit-details-marker]:hidden">
                      <span className="flex items-center justify-between gap-2">
                        Letter or complaint draft
                        <span className="text-xs font-normal text-lab-accent group-open:hidden">
                          Show
                        </span>
                        <span className="hidden text-xs font-normal text-lab-accent group-open:inline">
                          Hide
                        </span>
                      </span>
                    </summary>
                    <p className="mt-2 text-xs leading-relaxed text-lab-muted">
                      Use this language as a starting point. Adjust it to fit your situation — you
                      don&apos;t need to follow it word-for-word. Educational only — not legal advice.
                    </p>
                    <pre className="mt-3 max-h-[min(50vh,420px)] overflow-auto whitespace-pre-wrap text-xs leading-relaxed text-lab-muted">
                      {programAction.documentDraft}
                    </pre>
                    <button
                      type="button"
                      onClick={() => void copyDraft(programAction.documentDraft ?? "")}
                      className="mt-3 rounded-lg border border-white/[0.12] px-3 py-2 text-xs font-semibold text-lab-accent hover:bg-white/[0.04]"
                    >
                      {copiedDraft ? "Copied" : "Copy draft"}
                    </button>
                    {programAction.type === "cfpb_complaint" ? (
                      <a
                        href="https://www.consumerfinance.gov/complaint/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-3 inline-block text-xs font-semibold text-lab-accent hover:text-zinc-100"
                      >
                        Open CFPB complaint site ↗
                      </a>
                    ) : null}
                  </details>
                ) : null}

                {programAction?.callBullets && programAction.callBullets.length > 0 ? (
                  <div className="rounded-xl border border-white/[0.1] bg-lab-surface/90 px-4 py-4">
                    <h2 className="text-sm font-semibold text-lab-text">Call talking points</h2>
                    <p className="mt-1 text-xs text-lab-muted">
                      Use these as prompts — adapt the wording to sound like you. Nothing here has to
                      be memorized word-for-word.
                    </p>
                    <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-lab-muted">
                      {programAction.callBullets.map((b, i) => (
                        <li key={i}>{b}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {action && action.steps.length > 0 ? (
                  <div>
                    <h2 className="text-sm font-semibold text-lab-text">Steps</h2>
                    <p className="mt-1 text-xs text-lab-subtle">
                      Work in order when it helps — skip or revisit a step if your situation calls for
                      it.
                    </p>
                    <ol className="mt-4 space-y-3">
                      {action.steps.map((s, i) => (
                        <li
                          key={i}
                          className="flex gap-3 rounded-xl border border-white/[0.08] bg-lab-bg/50 px-4 py-3.5 text-sm leading-relaxed text-lab-muted"
                        >
                          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-zinc-600/45 bg-white/[0.06] text-xs font-bold text-zinc-300">
                            {i + 1}
                          </span>
                          <span className="min-w-0 pt-0.5">{s}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}

                {action?.callScript?.trim() ? (
                  <details className="details-calm group rounded-xl border border-white/[0.1] bg-lab-surface/90 px-4 py-3 open:pb-4">
                    <summary className="cursor-pointer list-none text-sm font-semibold text-lab-text [&::-webkit-details-marker]:hidden">
                      <span className="flex items-center justify-between gap-2">
                        Call script (optional detail)
                        <span className="text-xs font-normal text-lab-accent group-open:hidden">
                          Show
                        </span>
                        <span className="hidden text-xs font-normal text-lab-accent group-open:inline">
                          Hide
                        </span>
                      </span>
                    </summary>
                    <p className="mt-2 text-xs leading-relaxed text-lab-muted">
                      Use this language as a starting point. Adjust to fit your situation — you do
                      not need to memorize this word-for-word.
                    </p>
                    <p className="mt-3 text-sm leading-relaxed text-lab-muted">{action.callScript}</p>
                    <button
                      type="button"
                      onClick={() => void copyScript()}
                      className="mt-3 rounded-lg border border-white/[0.12] px-3 py-2 text-xs font-semibold text-lab-accent hover:bg-white/[0.04]"
                    >
                      {copiedScript ? "Copied" : "Copy script"}
                    </button>
                  </details>
                ) : null}

                {action && action.links.length > 0 ? (
                  <div>
                    <h2 className="text-sm font-semibold text-lab-text">Helpful links</h2>
                    <ul className="mt-2 space-y-2">
                      {action.links.map((l) => (
                        <li key={l.url}>
                          <a
                            href={l.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-lab-accent hover:text-zinc-100"
                          >
                            {l.label} ↗
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : null}

            {!loading &&
            !error &&
            hasContent &&
            !showRecoveryMissing &&
            !showRecoveryInvalid &&
            !showRecoveryEmpty ? (
              <motion.div
                variants={headerVariants}
                className="mt-10 space-y-4 rounded-xl border border-white/[0.08] bg-lab-surface/40 px-4 py-5 text-center sm:px-6"
              >
                <p className="text-sm font-semibold text-lab-text">
                  Ready to work through this next-step path?
                </p>
                <p className="text-sm leading-relaxed text-lab-muted">
                  Use this checklist as your guide, then return to Tracking, Responses, or
                  Escalation as needed. You can move at your own pace.
                </p>
                <NavLinksRow className="pt-1" />
              </motion.div>
            ) : null}

            <p className="mt-10 text-center text-[11px] leading-relaxed text-lab-subtle">
              Educational only — not legal advice. You choose what fits your situation.
            </p>
          </motion.div>
        ) : null}
      </StepMainColumn>
    </div>
  );
}
