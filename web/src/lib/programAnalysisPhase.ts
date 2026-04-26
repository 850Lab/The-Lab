/**
 * ORION-led org program analysis substeps (850 Lab).
 * Client-only sequencing — advances UX after report findings load.
 */

export const PROGRAM_ANALYSIS_PHASES = [
  "ANALYSIS_INTRO",
  "ANALYSIS_PRIORITIES",
  "ANALYSIS_REVIEW",
  "ANALYSIS_CONFIRMATION",
  "STRATEGY_HANDOFF",
] as const;

export type ProgramAnalysisPhase = (typeof PROGRAM_ANALYSIS_PHASES)[number];

export type ProgramAnalysisConfirmationStance =
  | "confirm_for_strategy"
  | "remove_from_review"
  | "mark_closer_look";

export type ProgramAnalysisPersisted = {
  phase: ProgramAnalysisPhase;
  reviewCardIndex: number;
  stancesByClaimId: Record<string, ProgramAnalysisConfirmationStance>;
};

const STORAGE_PREFIX = "850lab:programAnalysis:v1:";

function storageKey(reportId: number): string {
  return `${STORAGE_PREFIX}${reportId}`;
}

const VALID_STANCES: ProgramAnalysisConfirmationStance[] = [
  "confirm_for_strategy",
  "remove_from_review",
  "mark_closer_look",
];

function sanitizeStances(
  raw: Record<string, ProgramAnalysisConfirmationStance>,
): Record<string, ProgramAnalysisConfirmationStance> {
  const out: Record<string, ProgramAnalysisConfirmationStance> = {};
  for (const [k, v] of Object.entries(raw)) {
    if (VALID_STANCES.includes(v)) out[k] = v;
  }
  return out;
}

export function loadProgramAnalysisPersisted(reportId: number | null): ProgramAnalysisPersisted | null {
  if (reportId == null || typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(storageKey(reportId));
    if (!raw) return null;
    const j = JSON.parse(raw) as unknown;
    if (!j || typeof j !== "object") return null;
    const o = j as Record<string, unknown>;
    const phase = o.phase;
    if (!(PROGRAM_ANALYSIS_PHASES as readonly string[]).includes(String(phase))) return null;
    const reviewCardIndex = Number(o.reviewCardIndex);
    const stances = o.stancesByClaimId;
    return {
      phase: phase as ProgramAnalysisPhase,
      reviewCardIndex: Number.isFinite(reviewCardIndex) ? Math.max(0, reviewCardIndex) : 0,
      stancesByClaimId: sanitizeStances(
        stances && typeof stances === "object" && !Array.isArray(stances)
          ? (stances as Record<string, ProgramAnalysisConfirmationStance>)
          : {},
      ),
    };
  } catch {
    return null;
  }
}

export function saveProgramAnalysisPersisted(reportId: number | null, value: ProgramAnalysisPersisted): void {
  if (reportId == null || typeof window === "undefined") return;
  try {
    sessionStorage.setItem(storageKey(reportId), JSON.stringify(value));
  } catch {
    /* ignore quota / private mode */
  }
}

export function defaultPersistedForClaims(
  claimIds: string[],
  partial?: Partial<Pick<ProgramAnalysisPersisted, "phase" | "reviewCardIndex">>,
): ProgramAnalysisPersisted {
  const stances: Record<string, ProgramAnalysisConfirmationStance> = {};
  for (const id of claimIds) {
    stances[id] = "confirm_for_strategy";
  }
  return {
    phase: partial?.phase ?? "ANALYSIS_INTRO",
    reviewCardIndex: partial?.reviewCardIndex ?? 0,
    stancesByClaimId: stances,
  };
}
