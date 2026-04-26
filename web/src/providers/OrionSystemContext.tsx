import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import type { OrionBehavior } from "@/lib/orion/orionBehavior";
import { ORION_BEHAVIOR } from "@/lib/orion/orionBehavior";
import type { OrionCaseStripItem } from "@/lib/orion/orionCaseStrip";
import { buildOrionCaseStrip, type OrionCaseStripContext } from "@/lib/orion/orionCaseStrip";

export type OrionSurfacePayload = {
  /** Stable key for subtle enter transition */
  stateKey: string;
  behavior: OrionBehavior;
  caseStrip: OrionCaseStripItem[];
  /** Optional line under main message (e.g. current prepared issue) */
  accentLine?: string | null;
  /** Override rotating lines for this surface */
  rotatingOverride?: readonly string[] | null;
  /** Hub / resume: replaces `behavior.nextAction` without cloning behavior */
  nextActionOverride?: string | null;
};

export type OrionPanelModel = OrionSurfacePayload;

type OrionSystemContextValue = {
  surface: OrionSurfacePayload | null;
  setSurface: (next: OrionSurfacePayload | null) => void;
  /** Helper for pages that only have strip context */
  buildStrip: (ctx: OrionCaseStripContext) => OrionCaseStripItem[];
};

const OrionSystemContext = createContext<OrionSystemContextValue | null>(null);

export function OrionSystemProvider({ children }: { children: ReactNode }) {
  const [surface, setSurface] = useState<OrionSurfacePayload | null>(null);

  const buildStrip = useCallback((ctx: OrionCaseStripContext) => buildOrionCaseStrip(ctx), []);

  const value = useMemo(
    () => ({
      surface,
      setSurface,
      buildStrip,
    }),
    [surface, buildStrip],
  );

  return <OrionSystemContext.Provider value={value}>{children}</OrionSystemContext.Provider>;
}

export function useOrionSystem(): OrionSystemContextValue {
  const ctx = useContext(OrionSystemContext);
  if (!ctx) {
    throw new Error("useOrionSystem must be used within OrionSystemProvider");
  }
  return ctx;
}

/** Safe optional consumer (e.g. layout outside provider during tests). */
export function useOrionSystemOptional(): OrionSystemContextValue | null {
  return useContext(OrionSystemContext);
}

export function defaultOrionSurface(): OrionSurfacePayload {
  return {
    stateKey: "idle",
    behavior: ORION_BEHAVIOR.idle,
    caseStrip: buildOrionCaseStrip({
      enrolled: true,
      reportAnalyzed: false,
      reviewSetPrepared: false,
      strategyStepActive: false,
    }),
  };
}

