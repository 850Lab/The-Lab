import { describe, expect, it } from "vitest";
import {
  buildOrionViewModel,
  collectOrionPayloadSource,
  contractCompletenessFromFallbackMode,
  resolvePrimaryRenderable,
  resolveSupportingRenderables,
} from "./orionViewModel";

const fullUx = {
  primarySurface: {
    surfaceType: "warning_banner",
    attentionLevel: "dominant",
    renderIntent: "warning",
    contentSource: "guidance",
    actionPresentation: "secondary_cta",
    reasonCode: "warning_guidance_maps_to_banner",
  },
  supportingSurfaces: [
    {
      surfaceType: "inline_card",
      attentionLevel: "supportive",
      renderIntent: "warning",
      contentSource: "best_action",
      actionPresentation: "secondary_cta",
      reasonCode: "best_action_maps_to_support_surface",
    },
    {
      surfaceType: "support_strip",
      attentionLevel: "supportive",
      renderIntent: "warning",
      contentSource: "best_action_explanation",
      actionPresentation: "informational_only",
      reasonCode: "explanation_maps_to_support_surface",
    },
  ],
  surfaceContractVersion: "orion_ux_surface_contract_v1",
};

const fullDp = {
  primaryFocus: { kind: "guidance", emphasis: "high", reasonCode: "warning_guidance_dominates" },
  secondarySupport: [],
  suppressedSignals: [],
  prioritizationVersion: "orion_delivery_prioritization_v1",
};

describe("contractCompletenessFromFallbackMode", () => {
  it("maps fallback modes for analytics without changing semantics", () => {
    expect(contractCompletenessFromFallbackMode("full_contract")).toBe("full");
    expect(contractCompletenessFromFallbackMode("partial_contract")).toBe("partial");
    expect(contractCompletenessFromFallbackMode("legacy_fallback")).toBe("legacy");
    expect(contractCompletenessFromFallbackMode("none")).toBe("legacy");
  });
});

describe("buildOrionViewModel", () => {
  it("full contract normalization", () => {
    const vm = buildOrionViewModel({
      guidance: { type: "warning", message: "Stop" },
      bestAction: { actionKey: "retry_upload", label: "Retry" },
      actionCandidates: [],
      bestActionExplanation: { summary: "Because" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: fullUx,
    });
    expect(vm.fallbackMode).toBe("full_contract");
    expect(vm.contractCompleteness).toBe("full");
    expect(vm.hasOrion).toBe(true);
    expect(vm.primaryRenderable.surfaceType).toBe("warning_banner");
    expect(vm.primaryRenderable.kind).toBe("guidance");
  });

  it("partial contract when contracts incomplete", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "Required", explanationType: "requirement" },
    });
    expect(vm.fallbackMode).toBe("partial_contract");
    expect(vm.contractCompleteness).toBe("partial");
    expect(vm.primaryRenderable.kind).toBe("best_action");
  });

  it("legacy fallback when no ORION fields", () => {
    const vm = buildOrionViewModel({
      actionResult: "ok",
      workflowState: {},
      stepStatus: [],
      userMessage: "",
      nextAvailableActions: [],
    });
    expect(vm.fallbackMode).toBe("legacy_fallback");
    expect(vm.contractCompleteness).toBe("legacy");
    expect(vm.hasOrion).toBe(false);
  });

  it("warning full contract keeps guidance primary (no local reprioritization to best action)", () => {
    const vm = buildOrionViewModel({
      guidance: { type: "warning", message: "Warn" },
      bestAction: { actionKey: "retry_upload", label: "Retry", description: "x" },
      actionCandidates: [],
      bestActionExplanation: { summary: "Expl" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: fullUx,
    });
    const p = resolvePrimaryRenderable(vm);
    expect(p.kind).toBe("guidance");
    expect(p.content?.message).toBe("Warn");
  });

  it("waiting contract maps to passive primary", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "wait_for_processing" },
      bestActionExplanation: { summary: "Hold on", explanationType: "waiting" },
      deliveryPrioritization: {
        primaryFocus: {
          kind: "explanation",
          emphasis: "high",
          reasonCode: "waiting_state_explanation_primary",
        },
        secondarySupport: [],
        suppressedSignals: [],
        prioritizationVersion: "orion_delivery_prioritization_v1",
      },
      uxSurfaceContract: {
        primarySurface: {
          surfaceType: "passive_status",
          attentionLevel: "strong",
          renderIntent: "waiting",
          contentSource: "best_action_explanation",
          actionPresentation: "informational_only",
          reasonCode: "waiting_posture_maps_to_passive_status",
        },
        supportingSurfaces: [],
        surfaceContractVersion: "orion_ux_surface_contract_v1",
      },
    });
    expect(vm.fallbackMode).toBe("full_contract");
    expect(vm.primaryRenderable.surfaceType).toBe("passive_status");
    expect(vm.primaryRenderable.renderIntent).toBe("waiting");
  });

  it("requirement best action hero in partial mode", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay" },
      bestActionExplanation: { explanationType: "requirement", summary: "Need pay" },
    });
    expect(vm.primaryRenderable.renderIntent).toBe("requirement");
    expect(vm.primaryRenderable.surfaceType).toBe("hero_panel");
  });

  it("review action inline card in partial mode", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "review_claims", actionType: "review" },
      bestActionExplanation: { explanationType: "review" },
    });
    expect(vm.primaryRenderable.surfaceType).toBe("inline_card");
    expect(vm.primaryRenderable.renderIntent).toBe("review");
  });

  it("completed maps to completion_status", () => {
    const vm = buildOrionViewModel({
      workflowState: { overallStatus: "completed" },
      deliveryPrioritization: {
        primaryFocus: {
          kind: "status",
          emphasis: "high",
          reasonCode: "completed_state_no_primary_action",
        },
        secondarySupport: [],
        suppressedSignals: [],
        prioritizationVersion: "orion_delivery_prioritization_v1",
      },
      uxSurfaceContract: {
        primarySurface: {
          surfaceType: "completion_status",
          attentionLevel: "quiet",
          renderIntent: "completion",
          contentSource: "status",
          actionPresentation: "none",
          reasonCode: "completed_posture_maps_to_completion_status",
        },
        supportingSurfaces: [],
        surfaceContractVersion: "orion_ux_surface_contract_v1",
      },
    });
    expect(vm.primaryRenderable.surfaceType).toBe("completion_status");
    expect(vm.supportingRenderables.length).toBe(0);
  });

  it("supporting renderables cap at 2", () => {
    const vm = buildOrionViewModel({
      guidance: { type: "warning", message: "W" },
      bestAction: { actionKey: "retry_upload" },
      bestActionExplanation: { summary: "E" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: {
        ...fullUx,
        supportingSurfaces: [
          ...(fullUx.supportingSurfaces as object[]),
          {
            surfaceType: "candidate_list",
            attentionLevel: "quiet",
            renderIntent: "review",
            contentSource: "candidate_list",
            actionPresentation: "secondary_cta",
            reasonCode: "extra",
          },
        ],
      },
    });
    expect(vm.supportingRenderables.length).toBeLessThanOrEqual(2);
  });

  it("null safety", () => {
    expect(() => buildOrionViewModel(null)).not.toThrow();
    const vm = buildOrionViewModel(null);
    expect(vm.contractCompleteness).toBe("legacy");
    expect(resolvePrimaryRenderable(vm).content).toBeNull();
    expect(resolveSupportingRenderables(vm)).toEqual([]);
  });

  it("collectOrionPayloadSource merges nested workflow", () => {
    const src = collectOrionPayloadSource({
      userMessage: "x",
      workflow: {
        bestAction: { actionKey: "complete_payment" },
        uxSurfaceContract: fullUx,
        deliveryPrioritization: fullDp,
      },
    });
    expect((src.bestAction as { actionKey: string }).actionKey).toBe("complete_payment");
  });
});
