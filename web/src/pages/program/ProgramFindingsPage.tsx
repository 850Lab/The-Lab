import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getMeFindings } from "@/lib/orgProgramApi";
import type { FindingsResponse } from "@/lib/orgProgramTypes";
import { PROGRAM_EYEBROW } from "@/lib/orgProgramRoutes";
import { useAuth } from "@/providers/AuthContext";
import { ProgramAnalysisPhaseProvider, useProgramAnalysisPhase } from "@/hooks/useProgramAnalysisPhase";
import { useOrionProgramAdvancement } from "@/hooks/useOrionProgramAdvancement";
import { ORION_PROGRAM_FLOW } from "@/lib/orionProgramFlow";
import type { OrionBehaviorStateId } from "@/lib/orion/orionBehavior";
import { ORION_BEHAVIOR } from "@/lib/orion/orionBehavior";
import type { OrionCaseStripContext } from "@/lib/orion/orionCaseStrip";
import { useOrionSystem } from "@/providers/OrionSystemContext";
import {
  buildProgramAnalysisFindings,
  groupFindingsByTier,
} from "@/lib/programAnalysisFindings";
import { ProgramAnalysisPhaseSteps } from "@/components/program/ProgramAnalysisPhaseSteps";
import { ProgramAnalysisPrioritizedTiers } from "@/components/program/ProgramAnalysisPrioritizedTiers";
import { ProgramAnalysisReviewCard } from "@/components/program/ProgramAnalysisReviewCard";
import { ProgramAnalysisConfirmationPanel } from "@/components/program/ProgramAnalysisConfirmationPanel";

type PhaseBodyProps = {
  data: FindingsResponse | null;
  loading: boolean;
  err: string | null;
  findings: ReturnType<typeof buildProgramAnalysisFindings>;
  byTier: ReturnType<typeof groupFindingsByTier>;
  compactPhaseRail: boolean;
};

type AnalysisSurface = "loading" | "intake_complete" | "analysis";

function ProgramFindingsPhaseBody({
  data,
  loading,
  err,
  findings,
  byTier,
  compactPhaseRail,
}: PhaseBodyProps) {
  const { analysisPhase, persisted, setPhase, setReviewIndex, setStance, persist } =
    useProgramAnalysisPhase();
  const { setSurface, buildStrip } = useOrionSystem();

  const [surface, setSurfaceLocal] = useState<AnalysisSurface>("loading");

  useEffect(() => {
    if (loading) {
      setSurfaceLocal((s) => (s === "analysis" ? "analysis" : "loading"));
      return;
    }
    if (err || !data || data.processingStatus === "no_report") return;
    setSurfaceLocal((prev) => (prev === "loading" ? "intake_complete" : prev));
  }, [loading, data, err]);

  const handleAutoAdvance = useCallback((target: string) => {
    if (target === "ANALYSIS_INTRO") setSurfaceLocal("analysis");
  }, []);

  const reviewIdx = persisted?.reviewCardIndex ?? 0;
  const stances = persisted?.stancesByClaimId ?? {};
  const reviewFinding = findings[reviewIdx];

  useEffect(() => {
    if (!persisted || !compactPhaseRail) return;
    if (analysisPhase !== "ANALYSIS_INTRO" && analysisPhase !== "STRATEGY_HANDOFF") {
      setPhase("STRATEGY_HANDOFF");
    }
  }, [compactPhaseRail, persisted, analysisPhase, setPhase]);

  const confirmedCount = useMemo(
    () => findings.filter((f) => stances[f.id] !== "remove_from_review").length,
    [findings, stances],
  );
  const canConfirmationContinue = Boolean(
    ORION_PROGRAM_FLOW.ANALYSIS_CONFIRMATION.canAdvance?.({ confirmedCount }),
  );

  const advancementKey = useMemo(() => {
    if (surface === "intake_complete") return "REPORT_PROCESSING_COMPLETE";
    if (loading && surface !== "analysis") return "REPORT_PROCESSING";
    if (surface !== "analysis" || !persisted) return null;
    return analysisPhase as keyof typeof ORION_PROGRAM_FLOW;
  }, [surface, loading, persisted, analysisPhase]);

  const advancement = useOrionProgramAdvancement({
    stateKey: advancementKey,
    context: advancementKey === "ANALYSIS_CONFIRMATION" ? { confirmedCount } : undefined,
    enabled:
      advancementKey != null &&
      !err &&
      Boolean(data && data.processingStatus !== "no_report") &&
      !(loading && surface === "analysis"),
    externalGate:
      advancementKey === "STRATEGY_HANDOFF"
        ? canConfirmationContinue || findings.length === 0
        : true,
    onAutoAdvance: handleAutoAdvance,
  });

  const reviewAdvancement = useOrionProgramAdvancement({
    stateKey: surface === "analysis" && analysisPhase === "ANALYSIS_REVIEW" ? "ANALYSIS_REVIEW" : null,
    enabled: surface === "analysis" && analysisPhase === "ANALYSIS_REVIEW" && findings.length > 0,
    timerResetKey: reviewIdx,
  });

  useEffect(() => {
    if (err || !data || data.processingStatus === "no_report") {
      setSurface(null);
      return;
    }

    if (loading && surface !== "analysis") {
      setSurface({
        stateKey: "REPORT_PROCESSING",
        behavior: ORION_BEHAVIOR.REPORT_PROCESSING,
        caseStrip: buildStrip({
          enrolled: true,
          reportAnalyzed: false,
          reviewSetPrepared: false,
          strategyStepActive: false,
        }),
        rotatingOverride: ORION_BEHAVIOR.REPORT_PROCESSING.rotating ?? null,
      });
      return () => setSurface(null);
    }

    if (!persisted) {
      setSurface(null);
      return;
    }

    let behaviorId: OrionBehaviorStateId = "ANALYSIS_INTRO";
    if (surface === "intake_complete") behaviorId = "REPORT_PROCESSING_COMPLETE";
    else if (analysisPhase === "ANALYSIS_INTRO") behaviorId = "ANALYSIS_INTRO";
    else if (analysisPhase === "ANALYSIS_PRIORITIES") behaviorId = "ANALYSIS_PRIORITIES";
    else if (analysisPhase === "ANALYSIS_REVIEW") behaviorId = "ANALYSIS_REVIEW";
    else if (analysisPhase === "ANALYSIS_CONFIRMATION") behaviorId = "ANALYSIS_CONFIRMATION";
    else if (analysisPhase === "STRATEGY_HANDOFF") behaviorId = "STRATEGY_HANDOFF";

    const reportReady = Boolean(data && data.processingStatus !== "no_report");
    const stripCtx: OrionCaseStripContext = {
      enrolled: true,
      reportAnalyzed:
        reportReady &&
        (surface === "intake_complete" || surface === "analysis") &&
        !(loading && surface !== "analysis"),
      reviewSetPrepared:
        surface === "analysis" &&
        (analysisPhase === "ANALYSIS_CONFIRMATION" || analysisPhase === "STRATEGY_HANDOFF"),
      strategyStepActive: surface === "analysis" && analysisPhase === "STRATEGY_HANDOFF",
    };

    let accent: string | null = null;
    if (behaviorId === "ANALYSIS_REVIEW" && reviewFinding) {
      accent = `Introducing prepared issue ${reviewIdx + 1} of ${findings.length}: ${reviewFinding.orionInterpretation}`;
    }
    if (behaviorId === "ANALYSIS_INTRO" && findings.length === 0) {
      accent = "No discrete prepared issues were split out this pass — you can still move forward.";
    }

    setSurface({
      stateKey: `${behaviorId}-${surface}`,
      behavior: ORION_BEHAVIOR[behaviorId],
      caseStrip: buildStrip(stripCtx),
      accentLine: accent,
      rotatingOverride: null,
    });

    return () => setSurface(null);
  }, [
    err,
    data,
    loading,
    surface,
    persisted,
    analysisPhase,
    findings.length,
    reviewIdx,
    reviewFinding?.id,
    reviewFinding?.orionInterpretation,
    buildStrip,
    setSurface,
  ]);

  if (loading && surface !== "analysis") {
    return (
      <div className="space-y-8">
        <header className="space-y-3">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">{PROGRAM_EYEBROW}</p>
        </header>
        <p className="text-xs text-lab-subtle" role="status">
          One moment…
        </p>
      </div>
    );
  }

  if (err) {
    return (
      <div className="rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
        <p className="font-medium text-red-100">We couldn&apos;t load this view</p>
        <p className="mt-1 text-red-200/90">{err}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            to="/program/upload"
            className="inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-zinc-950 hover:brightness-110"
          >
            Share your report
          </Link>
          <Link to="/program" className="inline-flex items-center text-sm text-lab-accent hover:underline">
            Program hub
          </Link>
          <Link to="/" className="inline-flex items-center text-sm text-lab-muted hover:text-lab-text hover:underline">
            Home
          </Link>
        </div>
      </div>
    );
  }

  if (!data || data.processingStatus === "no_report") {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-6">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
          {PROGRAM_EYEBROW}
        </p>
        <h1 className="mt-2 text-xl font-semibold text-lab-text">Nothing to review yet</h1>
        <p className="mt-2 text-sm text-lab-muted">
          Share your bureau PDF first — we&apos;ll read it and bring the important pieces here.
        </p>
        <Link
          to="/program/upload"
          className="mt-4 inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-zinc-950"
        >
          Share your report
        </Link>
      </div>
    );
  }

  if (!persisted) {
    return (
      <p className="text-sm text-lab-muted" role="status">
        Preparing your ORION review…
      </p>
    );
  }

  const goHandoff = () => {
    persist({ ...persisted, phase: "STRATEGY_HANDOFF", reviewCardIndex: 0 });
  };

  const preparedForStrategy = findings.filter((f) => stances[f.id] === "confirm_for_strategy").length;
  const heldCloser = findings.filter((f) => stances[f.id] === "mark_closer_look").length;
  const operationalSummaryParts: string[] = [];
  if (preparedForStrategy > 0) {
    operationalSummaryParts.push(
      `${preparedForStrategy} item${preparedForStrategy === 1 ? "" : "s"} ${preparedForStrategy === 1 ? "has" : "have"} been prepared for strategy.`,
    );
  }
  if (heldCloser > 0) {
    operationalSummaryParts.push(
      `${heldCloser} issue${heldCloser === 1 ? "" : "s"} ${heldCloser === 1 ? "has" : "have"} been held for closer review.`,
    );
  }
  const operationalSummaryText =
    operationalSummaryParts.length > 0 ? operationalSummaryParts.join(" ") : undefined;

  const showPhaseRail = surface === "analysis" && persisted;

  return (
    <div className="space-y-8">
      <header className="space-y-3">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">{PROGRAM_EYEBROW}</p>
        {showPhaseRail ? (
          <ProgramAnalysisPhaseSteps active={analysisPhase} compact={compactPhaseRail} />
        ) : null}
      </header>

      {surface === "intake_complete" ? (
        <p className="text-xs text-lab-subtle transition-opacity duration-200" role="status">
          Taking you into your Case Review…
        </p>
      ) : null}

      {surface === "analysis" && analysisPhase === "ANALYSIS_INTRO" ? (
        <div className="space-y-4">
          <p className="text-sm text-lab-muted">
            Your Case Review is prioritized — we&apos;ll move forward together before strategy is prepared.
          </p>
          <button
            type="button"
            onClick={() => setPhase(findings.length ? "ANALYSIS_PRIORITIES" : "STRATEGY_HANDOFF")}
            disabled={!advancement.primaryActionEnabled}
            className="rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 transition-opacity duration-200 hover:brightness-110 disabled:pointer-events-none disabled:opacity-35"
          >
            {findings.length
              ? advancement.ctaLabel ?? ORION_PROGRAM_FLOW.ANALYSIS_INTRO.ctaLabel
              : "Continue"}
          </button>
        </div>
      ) : null}

      {surface === "analysis" && analysisPhase === "ANALYSIS_PRIORITIES" && findings.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">Case Review</p>
          <ProgramAnalysisPrioritizedTiers
            byTier={byTier}
            ctaLabel={ORION_PROGRAM_FLOW.ANALYSIS_PRIORITIES.ctaLabel ?? "Walk review set"}
            ctaArmReady={advancement.primaryActionEnabled}
            onContinue={() => {
              setReviewIndex(0);
              setPhase("ANALYSIS_REVIEW");
            }}
          />
        </div>
      ) : null}

      {surface === "analysis" && analysisPhase === "ANALYSIS_REVIEW" && findings.length > 0 ? (
        <ProgramAnalysisReviewCard
          finding={findings[reviewIdx]!}
          index={reviewIdx}
          total={findings.length}
          nextCtaArmReady={reviewAdvancement.primaryActionEnabled}
          operationalSummary={operationalSummaryText}
          onBack={() => setReviewIndex(Math.max(0, reviewIdx - 1))}
          onNext={() => {
            if (reviewIdx >= findings.length - 1) {
              setPhase("ANALYSIS_CONFIRMATION");
              return;
            }
            setReviewIndex(reviewIdx + 1);
          }}
        />
      ) : null}

      {surface === "analysis" && analysisPhase === "ANALYSIS_CONFIRMATION" && findings.length > 0 ? (
        <ProgramAnalysisConfirmationPanel
          findings={findings}
          stancesByClaimId={stances}
          onSetStance={setStance}
          onBack={() => {
            setReviewIndex(Math.max(0, findings.length - 1));
            setPhase("ANALYSIS_REVIEW");
          }}
          onContinue={goHandoff}
          continueDisabled={!advancement.primaryActionEnabled}
          continueCtaLabel={advancement.ctaLabel ?? ORION_PROGRAM_FLOW.ANALYSIS_CONFIRMATION.ctaLabel ?? "Continue"}
          blockedMessage={advancement.blockedMessage}
          ctaRevealSoft={advancement.ctaRevealed}
        />
      ) : null}

      {surface === "analysis" && analysisPhase === "STRATEGY_HANDOFF" ? (
        <div className="space-y-4">
          {!canConfirmationContinue && findings.length > 0 ? (
            <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
              {ORION_PROGRAM_FLOW.ANALYSIS_CONFIRMATION.blockedMessage}
            </p>
          ) : null}
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            {!canConfirmationContinue && findings.length > 0 ? (
              <span className="inline-flex cursor-not-allowed justify-center rounded-md bg-lab-accent/35 px-5 py-2.5 text-sm font-semibold text-zinc-950/60">
                {ORION_PROGRAM_FLOW.STRATEGY_HANDOFF.ctaLabel}
              </span>
            ) : (
              <Link
                to="/program/select"
                className={[
                  "inline-flex justify-center rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 transition-opacity duration-200 hover:brightness-110",
                  !advancement.primaryActionEnabled ? "pointer-events-none opacity-35" : "",
                ].join(" ")}
                aria-disabled={!advancement.primaryActionEnabled}
                onClick={(e) => {
                  if (!advancement.primaryActionEnabled) e.preventDefault();
                }}
              >
                {ORION_PROGRAM_FLOW.STRATEGY_HANDOFF.ctaLabel}
              </Link>
            )}
            {findings.length > 0 ? (
              <button
                type="button"
                onClick={() => setPhase("ANALYSIS_CONFIRMATION")}
                className="text-center text-sm font-medium text-lab-accent hover:underline sm:text-left"
              >
                Adjust Review Set
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      <p className="text-xs text-lab-subtle">
        <Link to="/program" className="text-lab-muted hover:text-lab-accent hover:underline">
          Program hub
        </Link>
      </p>
    </div>
  );
}

export function ProgramFindingsPage() {
  const { token } = useAuth();
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setData(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setErr(null);
      try {
        const j = await getMeFindings(token);
        if (!cancelled) setData(j);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Could not load what we found");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const summaryRecord = data?.summary as Record<string, unknown> | null | undefined;
  const reportId =
    data?.reportId ??
    (summaryRecord?.reportId != null && Number.isFinite(Number(summaryRecord.reportId))
      ? Number(summaryRecord.reportId)
      : null);
  const claims = data?.reviewClaims ?? [];
  const findings = useMemo(() => buildProgramAnalysisFindings(claims), [claims]);
  const claimIds = useMemo(() => findings.map((f) => f.id), [findings]);
  const byTier = useMemo(() => groupFindingsByTier(findings), [findings]);
  const compactPhaseRail = findings.length === 0;

  const findingsLoading = Boolean(token) && loading;

  return (
    <ProgramAnalysisPhaseProvider
      reportId={reportId}
      claimIds={claimIds}
      findingsLoading={findingsLoading}
    >
      <ProgramFindingsPhaseBody
        data={data}
        loading={loading}
        err={err}
        findings={findings}
        byTier={byTier}
        compactPhaseRail={compactPhaseRail}
      />
    </ProgramAnalysisPhaseProvider>
  );
}
