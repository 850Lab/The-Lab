import { useCallback, useEffect, useMemo, useState } from "react";
import type { OrionAdvanceMode } from "@/lib/orion/orionFlowConfig";
import type { OrionFlowConfig } from "@/lib/orion/orionFlowConfig";
import { ORION_PROGRAM_FLOW, type OrionProgramFlowKey } from "@/lib/orionProgramFlow";
import { clampAutoAdvanceMs, clampCtaRevealMs } from "@/lib/orionProgramAdvancementTiming";

export type UseOrionProgramAdvancementParams = {
  stateKey: OrionProgramFlowKey | null;
  context?: unknown;
  enabled?: boolean;
  /** Combined with blocked-mode `canAdvance` (e.g. cohort rules). Defaults true. */
  externalGate?: boolean;
  onAutoAdvance?: (target: string) => void;
  /** When this changes, CTA reveal / auto-advance timers reset (same `stateKey`, new moment). */
  timerResetKey?: string | number;
};

export type OrionProgramAdvancementResult = {
  mode: OrionAdvanceMode | null;
  config: OrionFlowConfig | null;
  /** After reveal delay for guided/blocked (opacity / pointer-events). */
  ctaRevealed: boolean;
  /** Whether the primary control should be enabled (not disabled). */
  primaryActionEnabled: boolean;
  blockedMessage?: string;
  ctaLabel?: string;
};

function getConfig(key: OrionProgramFlowKey | null): OrionFlowConfig | null {
  if (!key) return null;
  return ORION_PROGRAM_FLOW[key] as OrionFlowConfig;
}

export function useOrionProgramAdvancement({
  stateKey,
  context,
  enabled = true,
  externalGate = true,
  onAutoAdvance,
  timerResetKey,
}: UseOrionProgramAdvancementParams): OrionProgramAdvancementResult {
  const config = useMemo(() => getConfig(stateKey), [stateKey]);
  const [ctaRevealed, setCtaRevealed] = useState(false);

  const blockedGateOpen = useMemo(() => {
    if (!config || config.mode !== "blocked") return true;
    const inner = config.canAdvance?.(context ?? {}) ?? true;
    return inner && externalGate;
  }, [config, context, externalGate]);

  const primaryActionEnabled = useMemo(() => {
    if (!enabled || !config) return false;
    if (config.mode === "auto") return true;
    if (config.mode === "guided") return ctaRevealed && externalGate;
    return blockedGateOpen && ctaRevealed;
  }, [enabled, config, ctaRevealed, externalGate, blockedGateOpen]);

  const stableOnAuto = useCallback(
    (target: string) => {
      onAutoAdvance?.(target);
    },
    [onAutoAdvance],
  );

  useEffect(() => {
    if (!enabled || !config || !stateKey) {
      setCtaRevealed(false);
      return;
    }

    setCtaRevealed(false);

    if (config.mode === "auto") {
      const target = config.autoAdvanceTo;
      if (!target) return;
      const delay = clampAutoAdvanceMs(config.autoAdvanceDelayMs);
      const t = window.setTimeout(() => stableOnAuto(target), delay);
      return () => window.clearTimeout(t);
    }

    if (config.mode === "guided" || config.mode === "blocked") {
      const delay = clampCtaRevealMs(config.ctaDelayMs);
      const t = window.setTimeout(() => setCtaRevealed(true), delay);
      return () => window.clearTimeout(t);
    }

    setCtaRevealed(true);
    return undefined;
  }, [enabled, config, stateKey, stableOnAuto, timerResetKey]);

  const blockedMessage =
    config?.mode === "blocked" && !blockedGateOpen ? config.blockedMessage : undefined;

  return {
    mode: config?.mode ?? null,
    config,
    ctaRevealed,
    primaryActionEnabled,
    blockedMessage,
    ctaLabel: config?.ctaLabel,
  };
}
