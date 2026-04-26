import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type {
  ProgramAnalysisConfirmationStance,
  ProgramAnalysisPersisted,
  ProgramAnalysisPhase,
} from "@/lib/programAnalysisPhase";
import {
  defaultPersistedForClaims,
  loadProgramAnalysisPersisted,
  PROGRAM_ANALYSIS_PHASES,
  saveProgramAnalysisPersisted,
} from "@/lib/programAnalysisPhase";
import type { OrionPhaseKey } from "@/lib/orionProgramAnalysisMessages";

function mergeStances(
  existing: Record<string, ProgramAnalysisConfirmationStance>,
  claimIds: string[],
): Record<string, ProgramAnalysisConfirmationStance> {
  const next = { ...existing };
  for (const id of claimIds) {
    if (!(id in next)) next[id] = "confirm_for_strategy";
  }
  for (const k of Object.keys(next)) {
    if (!claimIds.includes(k)) delete next[k];
  }
  return next;
}

function isValidPhase(p: string): p is ProgramAnalysisPhase {
  return (PROGRAM_ANALYSIS_PHASES as readonly string[]).includes(p);
}

export type ProgramAnalysisPhaseContextValue = {
  /** Key for `ORION[phase]` — includes `REPORT_PROCESSING` while findings are loading. */
  phase: OrionPhaseKey;
  /** Persisted analysis step for UI branching (never `REPORT_PROCESSING`). */
  analysisPhase: ProgramAnalysisPhase;
  persisted: ProgramAnalysisPersisted | null;
  setPhase: (phase: ProgramAnalysisPhase) => void;
  setReviewIndex: (reviewCardIndex: number) => void;
  setStance: (claimId: string, stance: ProgramAnalysisConfirmationStance) => void;
  persist: (next: ProgramAnalysisPersisted) => void;
};

const ProgramAnalysisPhaseContext = createContext<ProgramAnalysisPhaseContextValue | null>(null);

type ProviderProps = {
  reportId: number | null;
  claimIds: string[];
  /** True while GET findings is in flight. */
  findingsLoading: boolean;
  children: ReactNode;
};

export function ProgramAnalysisPhaseProvider({
  reportId,
  claimIds,
  findingsLoading,
  children,
}: ProviderProps) {
  const [persisted, setPersisted] = useState<ProgramAnalysisPersisted | null>(null);

  const claimKey = useMemo(() => claimIds.join("\u0001"), [claimIds]);

  useEffect(() => {
    if (reportId == null) {
      setPersisted(null);
      return;
    }
    if (claimIds.length === 0) {
      const loaded = loadProgramAnalysisPersisted(reportId);
      setPersisted(
        loaded && isValidPhase(loaded.phase)
          ? { ...loaded, stancesByClaimId: {}, reviewCardIndex: 0 }
          : { phase: "ANALYSIS_INTRO", reviewCardIndex: 0, stancesByClaimId: {} },
      );
      return;
    }
    const loaded = loadProgramAnalysisPersisted(reportId);
    const base =
      loaded && isValidPhase(loaded.phase)
        ? {
            phase: loaded.phase,
            reviewCardIndex: loaded.reviewCardIndex,
            stancesByClaimId: mergeStances(loaded.stancesByClaimId, claimIds),
          }
        : defaultPersistedForClaims(claimIds);
    const maxIdx = Math.max(0, claimIds.length - 1);
    if (base.reviewCardIndex > maxIdx) base.reviewCardIndex = maxIdx;
    setPersisted(base);
  }, [reportId, claimKey]);

  const persist = useCallback(
    (next: ProgramAnalysisPersisted) => {
      setPersisted(next);
      saveProgramAnalysisPersisted(reportId, next);
    },
    [reportId],
  );

  const setPhase = useCallback(
    (nextPhase: ProgramAnalysisPhase) => {
      if (!persisted) return;
      persist({ ...persisted, phase: nextPhase });
    },
    [persist, persisted],
  );

  const setReviewIndex = useCallback(
    (reviewCardIndex: number) => {
      if (!persisted) return;
      persist({ ...persisted, reviewCardIndex });
    },
    [persist, persisted],
  );

  const setStance = useCallback(
    (claimId: string, stance: ProgramAnalysisConfirmationStance) => {
      if (!persisted) return;
      persist({
        ...persisted,
        stancesByClaimId: { ...persisted.stancesByClaimId, [claimId]: stance },
      });
    },
    [persist, persisted],
  );

  const analysisPhase: ProgramAnalysisPhase = persisted?.phase ?? "ANALYSIS_INTRO";

  const phase: OrionPhaseKey = findingsLoading
    ? "REPORT_PROCESSING"
    : persisted
      ? persisted.phase
      : "ANALYSIS_INTRO";

  const value = useMemo(
    () => ({
      phase,
      analysisPhase,
      persisted,
      setPhase,
      setReviewIndex,
      setStance,
      persist,
    }),
    [phase, analysisPhase, persisted, setPhase, setReviewIndex, setStance, persist],
  );

  return (
    <ProgramAnalysisPhaseContext.Provider value={value}>{children}</ProgramAnalysisPhaseContext.Provider>
  );
}

export function useProgramAnalysisPhase(): ProgramAnalysisPhaseContextValue {
  const ctx = useContext(ProgramAnalysisPhaseContext);
  if (!ctx) {
    throw new Error("useProgramAnalysisPhase must be used within ProgramAnalysisPhaseProvider");
  }
  return ctx;
}

export type { OrionPhaseKey } from "@/lib/orionProgramAnalysisMessages";
