import { describe, expect, it } from "vitest";
import type { WorkflowIntegrityHints } from "@/lib/integrityHintsTypes";
import {
  integrityIsHardBlocking,
  lettersContinuePrimaryButtonClass,
  mailingTrackPrimaryButtonClass,
  orionNarrativeCoherent,
  orionStepHeroCopy,
  orionWaitingOrPassivePrimary,
  paymentRecommendedCheckoutButtonClass,
  pickIntegrityBannerSpec,
  resolveOrionAuthority,
} from "./orionAuthority";
import { buildOrionViewModel } from "./orionViewModel";

const fullDp = {
  primaryFocus: { kind: "best_action", emphasis: "high", reasonCode: "test_primary" },
  secondarySupport: [] as unknown[],
  suppressedSignals: [] as unknown[],
  prioritizationVersion: "orion_delivery_prioritization_v1",
};

function requirementHeroUx(
  contentSource: "best_action",
  actionPresentation: "primary_cta" | "secondary_cta" | "informational_only" = "primary_cta",
) {
  return {
    primarySurface: {
      surfaceType: "hero_panel",
      attentionLevel: "dominant",
      renderIntent: "requirement",
      contentSource,
      actionPresentation,
      reasonCode: "test_requirement_hero",
    },
    supportingSurfaces: [] as unknown[],
    surfaceContractVersion: "orion_ux_surface_contract_v1",
  };
}

function baseHints(over: Partial<WorkflowIntegrityHints>): WorkflowIntegrityHints {
  return {
    entitlementsButPaymentIncomplete: false,
    paymentCompletedButWrongStep: false,
    mailingDebitWithoutSend: false,
    proofIncomplete: false,
    mailBlocked: false,
    workflowStepMismatch: false,
    nextRequiredAction: "pay",
    ...over,
  };
}

describe("resolveOrionAuthority", () => {
  it("suppresses soft payment hint when ORION full_contract already says complete_payment", () => {
    const vm = buildOrionViewModel({
      bestAction: {
        actionKey: "complete_payment",
        label: "Finish payment",
        description: "Activate your round",
      },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "Pay to continue", whyNow: "Unlock letters next" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action"),
    });
    expect(vm.fallbackMode).toBe("full_contract");

    const h = baseHints({ entitlementsButPaymentIncomplete: true });
    const r = resolveOrionAuthority(vm, h);
    expect(r.shouldSuppressIntegrityBanner).toBe(true);
    expect(r.primaryNarrativeSource).toBe("orion");
    expect(pickIntegrityBannerSpec(h)).not.toBeNull();
  });

  it("does not suppress when contract is partial even if hints align", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "Need pay", explanationType: "requirement" },
    });
    expect(vm.fallbackMode).toBe("partial_contract");

    const h = baseHints({ entitlementsButPaymentIncomplete: true });
    const r = resolveOrionAuthority(vm, h);
    expect(r.shouldSuppressIntegrityBanner).toBe(false);
  });

  it("suppresses proof hint when ORION full_contract already says upload_proof_documents", () => {
    const vm = buildOrionViewModel({
      bestAction: {
        actionKey: "upload_proof_documents",
        label: "Add proof",
        description: "ID and address",
      },
      actionCandidates: [{ actionKey: "upload_proof_documents" }],
      bestActionExplanation: { summary: "Proof required", whyNow: "Mail partner needs this" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action"),
    });
    expect(vm.fallbackMode).toBe("full_contract");

    const h = baseHints({ proofIncomplete: true, nextRequiredAction: "proof" });
    const r = resolveOrionAuthority(vm, h);
    expect(r.shouldSuppressIntegrityBanner).toBe(true);
    expect(r.primaryNarrativeSource).toBe("orion");
  });

  it("never suppresses for hard-blocking integrity (mail)", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "Pay" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action"),
    });
    const h = baseHints({ mailBlocked: true });
    const r = resolveOrionAuthority(vm, h);
    expect(r.shouldSuppressIntegrityBanner).toBe(false);
    expect(r.primaryNarrativeSource).toBe("integrity");
  });

  it("does not suppress paymentCompletedButWrongStep (integrity narrative)", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "Pay" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action"),
    });
    const h = baseHints({ paymentCompletedButWrongStep: true });
    const r = resolveOrionAuthority(vm, h);
    expect(r.shouldSuppressIntegrityBanner).toBe(false);
    expect(r.primaryNarrativeSource).toBe("integrity");
  });
});

describe("ORION V1.8B payment", () => {
  const paymentFallback = {
    title: "Unlock letter preparation for this round",
    subtitle: "Default payment support copy when ORION is not primary.",
  };

  it("full_contract + soft entitlements hint suppresses banner (payment path)", () => {
    const vm = buildOrionViewModel({
      bestAction: {
        actionKey: "complete_payment",
        label: "Finish payment",
        description: "Activate your round",
      },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "Pay to continue", whyNow: "Unlock letters next" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action"),
    });
    const h = baseHints({ entitlementsButPaymentIncomplete: true });
    const r = resolveOrionAuthority(vm, h);
    expect(r.shouldSuppressIntegrityBanner).toBe(true);
    expect(r.primaryNarrativeSource).toBe("orion");
  });

  it("partial_contract + same soft hint does not suppress", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "Need pay", explanationType: "requirement" },
    });
    const h = baseHints({ entitlementsButPaymentIncomplete: true });
    expect(resolveOrionAuthority(vm, h).shouldSuppressIntegrityBanner).toBe(false);
  });

  it("hard-blocking step mismatch keeps banner (integrity visible for payment)", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "Pay" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action"),
    });
    const h = baseHints({ workflowStepMismatch: true });
    const r = resolveOrionAuthority(vm, h);
    expect(r.shouldSuppressIntegrityBanner).toBe(false);
    expect(r.primaryNarrativeSource).toBe("integrity");
  });

  it("when integrity owns narrative, hero uses fallbacks not ORION headline", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "ORION checkout headline" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "S", whyNow: "ORION why now" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action"),
    });
    const auth = resolveOrionAuthority(vm, baseHints({ workflowStepMismatch: true }));
    expect(auth.primaryNarrativeSource).toBe("integrity");
    const hero = orionStepHeroCopy(auth, vm, paymentFallback);
    expect(hero.title).toBe(paymentFallback.title);
    expect(hero.subtitle).toBe(paymentFallback.subtitle);
    expect(hero.ctaEmphasis).toBe("standard");
  });

  it("hero copy falls back when ORION is unavailable (no headline, no banner)", () => {
    const vm = buildOrionViewModel(null);
    const auth = resolveOrionAuthority(vm, null);
    expect(auth.primaryNarrativeSource).toBe("page");
    const hero = orionStepHeroCopy(auth, vm, paymentFallback);
    expect(hero.title).toBe(paymentFallback.title);
    expect(hero.subtitle).toBe(paymentFallback.subtitle);
    expect(hero.ctaEmphasis).toBe("standard");
  });

  it("when ORION is primary, hero uses label and whyNow; CTA emphasis follows actionPresentation", () => {
    const vm = buildOrionViewModel({
      bestAction: {
        actionKey: "complete_payment",
        label: "Finish payment",
        description: "Ignored when whyNow set",
      },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "S", whyNow: "This is why checkout matters now." },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action", "primary_cta"),
    });
    const auth = resolveOrionAuthority(vm, null);
    expect(auth.primaryNarrativeSource).toBe("orion");
    const hero = orionStepHeroCopy(auth, vm, paymentFallback);
    expect(hero.title).toBe("Finish payment");
    expect(hero.subtitle).toBe("This is why checkout matters now.");
    expect(hero.ctaEmphasis).toBe("dominant");
  });

  it("secondary_cta maps to standard emphasis; informational_only to muted", () => {
    const basePayload = {
      bestAction: { actionKey: "complete_payment", label: "Pay", description: "Desc" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "S", whyNow: "W" },
      deliveryPrioritization: fullDp,
    };
    const vmStandard = buildOrionViewModel({
      ...basePayload,
      uxSurfaceContract: requirementHeroUx("best_action", "secondary_cta"),
    });
    const vmMuted = buildOrionViewModel({
      ...basePayload,
      uxSurfaceContract: requirementHeroUx("best_action", "informational_only"),
    });
    const authS = resolveOrionAuthority(vmStandard, null);
    const authM = resolveOrionAuthority(vmMuted, null);
    expect(orionStepHeroCopy(authS, vmStandard, paymentFallback).ctaEmphasis).toBe("standard");
    expect(orionStepHeroCopy(authM, vmMuted, paymentFallback).ctaEmphasis).toBe("muted");
  });
});

describe("ORION V1.9 coherence helpers", () => {
  const waitingFullContractVm = buildOrionViewModel({
    bestAction: { actionKey: "wait_for_processing" },
    bestActionExplanation: { summary: "Hold on", whyNow: "Updates arrive on their own timeline." },
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

  it("orionNarrativeCoherent is true for full_contract + orion primary", () => {
    expect(waitingFullContractVm.fallbackMode).toBe("full_contract");
    const auth = resolveOrionAuthority(waitingFullContractVm, null);
    expect(auth.primaryNarrativeSource).toBe("orion");
    expect(orionNarrativeCoherent(auth, waitingFullContractVm)).toBe(true);
  });

  it("orionNarrativeCoherent is false for partial_contract even with a headline", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay now" },
      bestActionExplanation: { summary: "Need pay" },
    });
    const auth = resolveOrionAuthority(vm, null);
    expect(vm.fallbackMode).toBe("partial_contract");
    expect(orionNarrativeCoherent(auth, vm)).toBe(false);
  });

  it("orionWaitingOrPassivePrimary for passive tracking-style contract", () => {
    const auth = resolveOrionAuthority(waitingFullContractVm, null);
    expect(orionWaitingOrPassivePrimary(auth)).toBe(true);
  });

  it("orionWaitingOrPassivePrimary false for requirement hero (no aggressive-passive confusion)", () => {
    const vm = buildOrionViewModel({
      bestAction: { actionKey: "complete_payment", label: "Pay" },
      actionCandidates: [{ actionKey: "complete_payment" }],
      bestActionExplanation: { summary: "S", whyNow: "W" },
      deliveryPrioritization: fullDp,
      uxSurfaceContract: requirementHeroUx("best_action", "primary_cta"),
    });
    const auth = resolveOrionAuthority(vm, null);
    expect(orionWaitingOrPassivePrimary(auth)).toBe(false);
  });

  it("letters-style fallback hero when ORION absent keeps page fallbacks + standard CTA emphasis", () => {
    const vm = buildOrionViewModel(null);
    const auth = resolveOrionAuthority(vm, null);
    const fb = {
      title: "Your dispute letters are ready to review",
      subtitle: "Local letters subtitle about proof and mailing.",
    };
    const hero = orionStepHeroCopy(auth, vm, fb);
    expect(hero.title).toBe(fb.title);
    expect(hero.subtitle).toBe(fb.subtitle);
    expect(hero.ctaEmphasis).toBe("standard");
    expect(lettersContinuePrimaryButtonClass("standard")).toContain("border-lab-accent");
  });

  it("lettersContinuePrimaryButtonClass and mailingTrackPrimaryButtonClass are class-only deltas", () => {
    expect(lettersContinuePrimaryButtonClass("dominant")).toContain("btn-primary-step");
    expect(lettersContinuePrimaryButtonClass("muted")).toContain("border-white/15");
    expect(mailingTrackPrimaryButtonClass("dominant")).toContain("bg-lab-accent");
    expect(mailingTrackPrimaryButtonClass("muted")).toContain("border-white/15");
    expect(lettersContinuePrimaryButtonClass("dominant")).not.toBe(
      lettersContinuePrimaryButtonClass("muted"),
    );
  });
});

describe("paymentRecommendedCheckoutButtonClass", () => {
  it("varies only Tailwind strings by emphasis (no behavioral coupling)", () => {
    const dominant = paymentRecommendedCheckoutButtonClass("dominant");
    const muted = paymentRecommendedCheckoutButtonClass("muted");
    expect(dominant).toContain("bg-lab-accent");
    expect(muted).toContain("border-white/15");
    expect(dominant).not.toBe(muted);
    expect(dominant + muted).not.toMatch(/onClick|stripe|fetch/i);
  });
});

describe("integrityIsHardBlocking", () => {
  it("is true for mismatch, mail blocked, mailing debit", () => {
    expect(integrityIsHardBlocking(baseHints({ workflowStepMismatch: true }))).toBe(true);
    expect(integrityIsHardBlocking(baseHints({ mailBlocked: true }))).toBe(true);
    expect(integrityIsHardBlocking(baseHints({ mailingDebitWithoutSend: true }))).toBe(true);
  });

  it("is false for soft hints only", () => {
    expect(integrityIsHardBlocking(baseHints({ proofIncomplete: true }))).toBe(false);
    expect(integrityIsHardBlocking(baseHints({ entitlementsButPaymentIncomplete: true }))).toBe(
      false,
    );
  });
});
