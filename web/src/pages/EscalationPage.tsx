import { motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { EscalationProgramSection } from "@/components/EscalationProgramSection";
import { EscalationCTASection } from "@/components/EscalationCTASection";
import { EscalationOptionCard } from "@/components/EscalationOptionCard";
import { RecommendedActionCard } from "@/components/RecommendedActionCard";
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
import { escalationProgramBridgeCopy } from "@/lib/intelligenceExpression";

const QUICK_TO_ACTION: Record<EscalationOptionId, string> = {
  furnisher: "furnisher_dispute",
  reverify: "follow_up_letter",
  cfpb: "cfpb_complaint",
};

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.04 },
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

const stackVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.05 },
  },
};

const sublabelVariants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.36, ease: [0.22, 1, 0.36, 1] },
  },
};

function triggerSurfaceClass(severity: string): string {
  if (severity === "high") {
    return "border-amber-500/35 bg-amber-500/[0.07]";
  }
  return "border-white/[0.1] bg-lab-surface/85";
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

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[36%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[40%] z-0 h-[min(48vw,320px)] w-[min(48vw,320px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.04] blur-[90px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-28 pt-24 sm:max-w-lg sm:px-6 sm:pb-32 sm:pt-28">
        {!ctxLoading && (!token || !workflowId) ? (
          <p className="mt-10 text-center text-sm text-lab-muted">
            Sign in and open your program to load escalation tools tied to your mail and responses.
          </p>
        ) : null}
        {ctxLoading || (token && workflowId) ? (
        <motion.div variants={pageVariants} initial="hidden" animate="show" className="pb-4">
          <motion.p
            variants={headerVariants}
            className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
          >
            Leverage after responses
          </motion.p>
          <motion.h1
            variants={headerVariants}
            className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
          >
            {loading ? "Loading your escalation toolkit…" : layer?.leverageHeadline ?? "More power, not fewer options"}
          </motion.h1>
          <motion.p
            variants={headerVariants}
            className="mx-auto mt-3 max-w-md text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            {layer?.subcopy ??
              "If disputes are stuck, late, or half-fixed, you are not out of moves — furnisher disputes, written follow-ups, structured calls, and formal complaints are all on the table."}
          </motion.p>

          <motion.p
            variants={headerVariants}
            className="mx-auto mt-5 max-w-md rounded-xl border border-white/[0.08] bg-lab-surface/80 px-4 py-4 text-left text-sm leading-relaxed text-lab-muted sm:px-5 sm:text-[15px]"
          >
            {escalationProgramBridgeCopy()}
          </motion.p>

          {loadError ? (
            <motion.p
              variants={headerVariants}
              className="mt-6 text-center text-sm text-amber-200/95"
            >
              {loadError}
            </motion.p>
          ) : null}

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
                What triggered this toolkit
              </motion.p>
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
                Concrete leverage actions
              </motion.p>
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
                      className="shrink-0 text-xs font-semibold text-lab-accent hover:text-sky-300"
                    >
                      Full view →
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
                            className="text-sm font-medium text-lab-accent hover:text-sky-300"
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
              Quick picks (same paths, shorter cards)
            </motion.p>
            <RecommendedActionCard option={selected} />

            <motion.p
              variants={sublabelVariants}
              className="text-xs font-medium uppercase tracking-wide text-lab-subtle"
            >
              Choose a focus
            </motion.p>

            {ESCALATION_OPTIONS.map((opt) => (
              <EscalationOptionCard
                key={opt.id}
                option={opt}
                selected={selectedId === opt.id}
                onSelect={() => setSelectedId(opt.id)}
              />
            ))}
          </motion.div>

          <EscalationCTASection
            onContinue={handleContinue}
            footerHint="Opens a focused checklist for the path you selected."
          />

          <p className="mt-8 text-center text-[11px] leading-relaxed text-lab-subtle">
            Educational steps only — not legal advice. You decide what fits your situation.
          </p>
        </motion.div>
        ) : null}
      </main>
    </div>
  );
}
