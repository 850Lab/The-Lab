/**
 * ORION V1.6 — frontend consumption layer: normalize API payloads, do not re-prioritize
 * when backend contracts are present.
 *
 * ORION is deterministic. Do NOT inject AI logic here. AI layers must consume ORION outputs, not modify them.
 */

import type { WorkflowEnvelope } from "@/lib/workflowTypes";

export type OrionFallbackMode = "full_contract" | "partial_contract" | "legacy_fallback" | "none";

/** Coarse contract shape for analytics / drift — mirrors `fallbackMode`; does not change rendering. */
export type OrionContractCompleteness = "full" | "partial" | "legacy";

export function contractCompletenessFromFallbackMode(
  mode: OrionFallbackMode,
): OrionContractCompleteness {
  if (mode === "full_contract") return "full";
  if (mode === "partial_contract") return "partial";
  return "legacy";
}

export type OrionPrimaryKind =
  | "guidance"
  | "best_action"
  | "best_action_explanation"
  | "status"
  | null;

export type OrionPrimarySurfaceType =
  | "warning_banner"
  | "hero_panel"
  | "inline_card"
  | "passive_status"
  | "completion_status"
  | null;

export type OrionRenderIntent =
  | "warning"
  | "progress"
  | "waiting"
  | "requirement"
  | "review"
  | "completion"
  | "neutral"
  | null;

export type OrionActionPresentation =
  | "primary_cta"
  | "secondary_cta"
  | "informational_only"
  | "none"
  | null;

/** Resolved primary row: backend intent + concrete payload slice for rendering. */
export type OrionPrimaryRenderable = {
  kind: OrionPrimaryKind;
  surfaceType: OrionPrimarySurfaceType;
  renderIntent: OrionRenderIntent;
  actionPresentation: OrionActionPresentation;
  content: Record<string, unknown> | null;
  reasonCode: string | null;
};

export type OrionSupportingKind =
  | "guidance"
  | "best_action"
  | "best_action_explanation"
  | "candidate_list"
  | "status";

export type OrionSupportingSurfaceType =
  | "inline_card"
  | "passive_status"
  | "support_strip"
  | "candidate_list";

export type OrionSupportingRenderable = {
  kind: OrionSupportingKind;
  surfaceType: OrionSupportingSurfaceType;
  renderIntent: Exclude<OrionRenderIntent, "completion" | null>;
  actionPresentation: Exclude<OrionActionPresentation, null>;
  content: Record<string, unknown> | null;
  reasonCode: string | null;
};

export type OrionViewModel = {
  hasOrion: boolean;
  guidance: Record<string, unknown> | null;
  bestAction: Record<string, unknown> | null;
  actionCandidates: Record<string, unknown>[];
  bestActionExplanation: Record<string, unknown> | null;
  deliveryPrioritization: Record<string, unknown> | null;
  uxSurfaceContract: Record<string, unknown> | null;
  primaryRenderable: OrionPrimaryRenderable;
  supportingRenderables: OrionSupportingRenderable[];
  fallbackMode: OrionFallbackMode;
  contractCompleteness: OrionContractCompleteness;
};

function isRecord(v: unknown): v is Record<string, unknown> {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function asRecordOrNull(v: unknown): Record<string, unknown> | null {
  return isRecord(v) ? v : null;
}

function asRecordArray(v: unknown): Record<string, unknown>[] {
  if (!Array.isArray(v)) return [];
  return v.filter(isRecord);
}

/** Merge root payload with nested `workflow` (e.g. payment context) for ORION keys. */
export function collectOrionPayloadSource(payload: unknown): Record<string, unknown> {
  if (!isRecord(payload)) return {};
  const root = payload;
  const wf = root.workflow;
  if (isRecord(wf)) {
    return { ...root, ...wf };
  }
  return root;
}

function emptyPrimary(): OrionPrimaryRenderable {
  return {
    kind: null,
    surfaceType: null,
    renderIntent: null,
    actionPresentation: null,
    content: null,
    reasonCode: null,
  };
}

function hasCoreOrionFields(slice: {
  guidance: unknown;
  bestAction: unknown;
  actionCandidates: unknown;
  bestActionExplanation: unknown;
}): boolean {
  if (slice.guidance != null) return true;
  if (slice.bestAction != null) return true;
  if (Array.isArray(slice.actionCandidates) && slice.actionCandidates.length > 0) return true;
  if (slice.bestActionExplanation != null) return true;
  return false;
}

function hasContracts(slice: {
  deliveryPrioritization: unknown;
  uxSurfaceContract: unknown;
}): boolean {
  const dp = slice.deliveryPrioritization;
  const ux = slice.uxSurfaceContract;
  if (!isRecord(dp) || !isRecord(ux)) return false;
  return isRecord(dp.primaryFocus) && isRecord(ux.primarySurface);
}

function mapContentSourceToContent(
  source: string | undefined,
  vm: Pick<
    OrionViewModel,
    "guidance" | "bestAction" | "bestActionExplanation" | "actionCandidates"
  >,
): Record<string, unknown> | null {
  switch (source) {
    case "guidance":
      return vm.guidance;
    case "best_action":
      return vm.bestAction;
    case "best_action_explanation":
      return vm.bestActionExplanation;
    case "candidate_list":
      return { candidates: vm.actionCandidates };
    case "status":
      return null;
    default:
      return null;
  }
}

function primaryFromUxContract(
  ux: Record<string, unknown>,
  vmBase: Pick<
    OrionViewModel,
    "guidance" | "bestAction" | "bestActionExplanation" | "actionCandidates"
  >,
): OrionPrimaryRenderable {
  const ps = asRecordOrNull(ux.primarySurface);
  if (!ps) return emptyPrimary();
  const contentSource = String(ps.contentSource ?? "");
  return {
    kind:
      contentSource === "guidance"
        ? "guidance"
        : contentSource === "best_action"
          ? "best_action"
          : contentSource === "best_action_explanation"
            ? "best_action_explanation"
            : contentSource === "status"
              ? "status"
              : null,
    surfaceType: (ps.surfaceType as OrionPrimarySurfaceType) ?? null,
    renderIntent: (ps.renderIntent as OrionRenderIntent) ?? null,
    actionPresentation: (ps.actionPresentation as OrionActionPresentation) ?? null,
    content: mapContentSourceToContent(contentSource, vmBase),
    reasonCode: typeof ps.reasonCode === "string" ? ps.reasonCode : null,
  };
}

function supportingFromUxContract(
  ux: Record<string, unknown>,
  vmBase: Pick<
    OrionViewModel,
    "guidance" | "bestAction" | "bestActionExplanation" | "actionCandidates"
  >,
): OrionSupportingRenderable[] {
  const raw = ux.supportingSurfaces;
  if (!Array.isArray(raw)) return [];
  const out: OrionSupportingRenderable[] = [];
  for (const item of raw.slice(0, 2)) {
    if (!isRecord(item)) continue;
    const cs = String(item.contentSource ?? "");
    const kind: OrionSupportingKind | null =
      cs === "guidance"
        ? "guidance"
        : cs === "best_action"
          ? "best_action"
          : cs === "best_action_explanation"
            ? "best_action_explanation"
            : cs === "candidate_list"
              ? "candidate_list"
              : cs === "status"
                ? "status"
                : null;
    if (!kind) continue;
    const ri = (item.renderIntent as OrionRenderIntent) ?? "neutral";
    const safeIntent =
      ri === "completion" || ri == null ? "neutral" : (ri as Exclude<OrionRenderIntent, "completion" | null>);
    const ap = (item.actionPresentation as OrionActionPresentation) ?? "informational_only";
    const safeAp = ap ?? "informational_only";
    out.push({
      kind,
      surfaceType: (item.surfaceType as OrionSupportingSurfaceType) ?? "inline_card",
      renderIntent: safeIntent,
      actionPresentation: safeAp,
      content: mapContentSourceToContent(cs, vmBase),
      reasonCode: typeof item.reasonCode === "string" ? item.reasonCode : null,
    });
  }
  return out;
}

/** Minimal priority when contracts are absent (does not override full contract path). */
function buildPartialPrimary(
  guidance: Record<string, unknown> | null,
  bestAction: Record<string, unknown> | null,
  bestActionExplanation: Record<string, unknown> | null,
): OrionPrimaryRenderable {
  const gType = guidance ? String(guidance.type ?? "") : "";
  if (guidance && gType === "warning") {
    return {
      kind: "guidance",
      surfaceType: "warning_banner",
      renderIntent: "warning",
      actionPresentation: bestAction ? "secondary_cta" : "informational_only",
      content: guidance,
      reasonCode: "partial_fallback_warning_guidance_primary",
    };
  }
  if (bestAction) {
    const key = String(bestAction.actionKey ?? "");
    const explType = bestActionExplanation
      ? String(bestActionExplanation.explanationType ?? "")
      : "";
    let surface: OrionPrimarySurfaceType = "hero_panel";
    let intent: OrionRenderIntent = "progress";
    if (
      explType === "requirement" ||
      key === "complete_payment" ||
      key === "upload_proof_documents"
    ) {
      intent = "requirement";
      surface = "hero_panel";
    } else if (
      explType === "review" ||
      key.startsWith("review_") ||
      key === "check_tracking_status"
    ) {
      intent = "review";
      surface = "inline_card";
    } else if (explType === "waiting" || key === "wait_for_processing") {
      intent = "waiting";
      surface = "passive_status";
    }
    return {
      kind: "best_action",
      surfaceType: surface,
      renderIntent: intent,
      actionPresentation: "primary_cta",
      content: bestAction,
      reasonCode: "partial_fallback_best_action_primary",
    };
  }
  if (bestActionExplanation) {
    const et = String(bestActionExplanation.explanationType ?? "");
    const intent =
      et === "waiting"
        ? "waiting"
        : et === "requirement"
          ? "requirement"
          : et === "review"
            ? "review"
            : et === "warning"
              ? "warning"
              : "neutral";
    return {
      kind: "best_action_explanation",
      surfaceType: et === "waiting" ? "passive_status" : "inline_card",
      renderIntent: intent as OrionRenderIntent,
      actionPresentation: "informational_only",
      content: bestActionExplanation,
      reasonCode: "partial_fallback_explanation_primary",
    };
  }
  return emptyPrimary();
}

function buildPartialSupporting(
  primary: OrionPrimaryRenderable,
  vm: Pick<
    OrionViewModel,
    "guidance" | "bestAction" | "bestActionExplanation" | "actionCandidates"
  >,
): OrionSupportingRenderable[] {
  const out: OrionSupportingRenderable[] = [];
  const push = (r: OrionSupportingRenderable) => {
    if (out.length < 2) out.push(r);
  };
  if (primary.kind === "guidance" && vm.bestAction) {
    push({
      kind: "best_action",
      surfaceType: "inline_card",
      renderIntent: "progress",
      actionPresentation: "secondary_cta",
      content: vm.bestAction,
      reasonCode: "partial_support_best_action_under_guidance",
    });
  }
  if (primary.kind !== "best_action_explanation" && vm.bestActionExplanation) {
    const et = String(vm.bestActionExplanation.explanationType ?? "neutral");
    const ri = (et === "completion" ? "neutral" : et) as Exclude<
      OrionRenderIntent,
      "completion" | null
    >;
    push({
      kind: "best_action_explanation",
      surfaceType: "support_strip",
      renderIntent: ri,
      actionPresentation: "informational_only",
      content: vm.bestActionExplanation,
      reasonCode: "explanation_maps_to_support_surface",
    });
  }
  if (
    primary.kind === "best_action" &&
    vm.guidance &&
    String(vm.guidance.type ?? "") !== "warning"
  ) {
    push({
      kind: "guidance",
      surfaceType: "passive_status",
      renderIntent: "neutral",
      actionPresentation: "informational_only",
      content: vm.guidance,
      reasonCode: "guidance_maps_to_supporting_surface",
    });
  }
  return out.slice(0, 2);
}

/**
 * Normalize any customer workflow payload (resume envelope, nested `workflow`, etc.).
 */
export function buildOrionViewModel(
  payload: WorkflowEnvelope | Record<string, unknown> | null | undefined,
): OrionViewModel {
  const src = collectOrionPayloadSource(payload ?? null);
  const guidance = asRecordOrNull(src.guidance);
  const bestAction = asRecordOrNull(src.bestAction);
  const actionCandidates = asRecordArray(src.actionCandidates);
  const bestActionExplanation = asRecordOrNull(src.bestActionExplanation);
  const deliveryPrioritization = asRecordOrNull(src.deliveryPrioritization);
  const uxSurfaceContract = asRecordOrNull(src.uxSurfaceContract);

  const core = hasCoreOrionFields({
    guidance,
    bestAction,
    actionCandidates,
    bestActionExplanation,
  });
  const contracts = hasContracts({ deliveryPrioritization, uxSurfaceContract });
  const hasOrion =
    core ||
    deliveryPrioritization != null ||
    uxSurfaceContract != null;

  const vmBase = {
    guidance,
    bestAction,
    bestActionExplanation,
    actionCandidates,
  };

  let fallbackMode: OrionFallbackMode = "none";
  let primaryRenderable: OrionPrimaryRenderable = emptyPrimary();
  let supportingRenderables: OrionSupportingRenderable[] = [];

  if (!hasOrion) {
    fallbackMode = "legacy_fallback";
  } else if (contracts && uxSurfaceContract && deliveryPrioritization) {
    fallbackMode = "full_contract";
    primaryRenderable = primaryFromUxContract(uxSurfaceContract, vmBase);
    supportingRenderables = supportingFromUxContract(uxSurfaceContract, vmBase);
  } else {
    fallbackMode = "partial_contract";
    primaryRenderable = buildPartialPrimary(guidance, bestAction, bestActionExplanation);
    supportingRenderables = buildPartialSupporting(primaryRenderable, vmBase);
    if (uxSurfaceContract) {
      const uxp = primaryFromUxContract(uxSurfaceContract, vmBase);
      primaryRenderable = {
        ...primaryRenderable,
        kind: uxp.kind ?? primaryRenderable.kind,
        surfaceType: uxp.surfaceType ?? primaryRenderable.surfaceType,
        renderIntent: uxp.renderIntent ?? primaryRenderable.renderIntent,
        actionPresentation: uxp.actionPresentation ?? primaryRenderable.actionPresentation,
        content: uxp.content ?? primaryRenderable.content,
        reasonCode: uxp.reasonCode ?? primaryRenderable.reasonCode,
      };
      const uxs = supportingFromUxContract(uxSurfaceContract, vmBase);
      if (uxs.length > 0) supportingRenderables = uxs;
    }
  }

  return {
    hasOrion,
    guidance,
    bestAction,
    actionCandidates,
    bestActionExplanation,
    deliveryPrioritization,
    uxSurfaceContract,
    primaryRenderable,
    supportingRenderables,
    fallbackMode,
    contractCompleteness: contractCompletenessFromFallbackMode(fallbackMode),
  };
}

/**
 * Fills `content` on an existing primary renderable (idempotent if already set).
 */
export function resolvePrimaryRenderable(vm: OrionViewModel): OrionPrimaryRenderable {
  const p = vm.primaryRenderable;
  if (p.content != null) return p;
  const src = p.kind === "guidance" ? "guidance" : p.kind === "best_action" ? "best_action" : p.kind === "best_action_explanation" ? "best_action_explanation" : "status";
  const content =
    p.kind === "status"
      ? null
      : mapContentSourceToContent(src === "status" ? undefined : src, vm);
  return { ...p, content };
}

export function resolveSupportingRenderables(vm: OrionViewModel): OrionSupportingRenderable[] {
  return vm.supportingRenderables.map((s) => {
    if (s.content != null) return s;
    const cs =
      s.kind === "guidance"
        ? "guidance"
        : s.kind === "best_action"
          ? "best_action"
          : s.kind === "best_action_explanation"
            ? "best_action_explanation"
            : s.kind === "candidate_list"
              ? "candidate_list"
              : "status";
    const content = cs === "status" ? null : mapContentSourceToContent(cs, vm);
    return { ...s, content };
  });
}
