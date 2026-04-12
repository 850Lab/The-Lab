/**
 * ORION V1.8 — align narrative authority: ORION primary, integrity as constraint.
 *
 * ORION is deterministic. Do NOT inject AI logic here. AI layers must consume ORION outputs, not modify them.
 */

import type { WorkflowIntegrityHints } from "@/lib/integrityHintsTypes";
import { primaryHeadlineFromRenderable } from "@/lib/orion/orionSurfaceProps";
import type { OrionPrimaryRenderable } from "@/lib/orion/orionViewModel";
import {
  resolvePrimaryRenderable,
  type OrionViewModel,
} from "@/lib/orion/orionViewModel";

export type PrimaryNarrativeSource = "orion" | "integrity" | "page";

export type IntegrityBannerSpec = {
  title: string;
  body: string;
  ctaLabel: string;
};

/** Same ordering as legacy `WorkflowIntegrityBanner` pick — kept here as single source of truth. */
export function pickIntegrityBannerSpec(
  h: WorkflowIntegrityHints | null | undefined,
): IntegrityBannerSpec | null {
  if (!h) return null;
  if (h.workflowStepMismatch) {
    return {
      title: "We’ve moved you to the correct step",
      body: "Your place in the program was out of sync; use the button below to continue where you should be.",
      ctaLabel: "Go to current step",
    };
  }
  if (h.entitlementsButPaymentIncomplete) {
    return {
      title: "Finish activating your purchase",
      body: "Your letter credits are ready, but this step still needs to complete so the program can continue.",
      ctaLabel: "Continue",
    };
  }
  if (h.paymentCompletedButWrongStep) {
    return {
      title: "Payment is complete",
      body: "Continue from your current program step when you’re ready.",
      ctaLabel: "Continue",
    };
  }
  if (h.proofIncomplete) {
    return {
      title: "Upload ID and address proof before sending",
      body: "Certified mail requires government ID and proof of address on file.",
      ctaLabel: "Go to proof step",
    };
  }
  if (h.mailBlocked) {
    return {
      title: "Mailing is not available right now",
      body: "Sending is paused on the server (for example, Lob configuration). You can still move through other steps; try again later.",
      ctaLabel: "Continue",
    };
  }
  if (h.mailingDebitWithoutSend) {
    return {
      title: "We detected an issue with a previous send attempt",
      body: "A mailing credit was used without a matching mailed record. If this persists, contact support with your program / workflow id.",
      ctaLabel: "Continue",
    };
  }
  return null;
}

function actionKeyFromPrimary(p: OrionPrimaryRenderable): string {
  const c = p.content;
  if (!c || typeof c !== "object") return "";
  const k = (c as { actionKey?: unknown }).actionKey;
  return typeof k === "string" ? k : "";
}

/** Integrity states that must keep the banner visible and take narrative priority. */
export function integrityIsHardBlocking(h: WorkflowIntegrityHints | null | undefined): boolean {
  if (!h) return false;
  return h.workflowStepMismatch || h.mailBlocked || h.mailingDebitWithoutSend;
}

/**
 * Soft integrity hints that duplicate ORION when backend already surfaced the same next move
 * under full_contract.
 */
function integritySoftRedundantWithOrion(
  h: WorkflowIntegrityHints,
  primary: OrionPrimaryRenderable,
): boolean {
  const key = actionKeyFromPrimary(primary);
  const intent = primary.renderIntent;
  if (h.entitlementsButPaymentIncomplete) {
    return key === "complete_payment" || (intent === "requirement" && key === "complete_payment");
  }
  if (h.proofIncomplete) {
    return key === "upload_proof_documents" || (intent === "requirement" && key === "upload_proof_documents");
  }
  return false;
}

export type OrionAuthorityResult = {
  primaryNarrativeSource: PrimaryNarrativeSource;
  resolvedPrimaryRenderable: OrionPrimaryRenderable;
  integrityConstraint: WorkflowIntegrityHints | null;
  shouldSuppressIntegrityBanner: boolean;
};

export function resolveOrionAuthority(
  orionViewModel: OrionViewModel,
  integrityHints: WorkflowIntegrityHints | null | undefined,
): OrionAuthorityResult {
  const resolvedPrimaryRenderable = resolvePrimaryRenderable(orionViewModel);
  const h = integrityHints ?? null;

  const hard = integrityIsHardBlocking(h);
  const wrongStep = !!h?.paymentCompletedButWrongStep;
  const bannerSpec = pickIntegrityBannerSpec(h);

  let primaryNarrativeSource: PrimaryNarrativeSource;
  if (hard || wrongStep) {
    primaryNarrativeSource = "integrity";
  } else {
    const orionHeadline = primaryHeadlineFromRenderable(resolvedPrimaryRenderable);
    if (orionHeadline) {
      primaryNarrativeSource = "orion";
    } else if (bannerSpec) {
      primaryNarrativeSource = "integrity";
    } else {
      primaryNarrativeSource = "page";
    }
  }

  const shouldSuppressIntegrityBanner =
    h != null &&
    !hard &&
    !wrongStep &&
    bannerSpec != null &&
    orionViewModel.fallbackMode === "full_contract" &&
    integritySoftRedundantWithOrion(h, resolvedPrimaryRenderable);

  return {
    primaryNarrativeSource,
    resolvedPrimaryRenderable,
    integrityConstraint: h,
    shouldSuppressIntegrityBanner,
  };
}

export type OrionHeroCopy = {
  title: string;
  subtitle: string;
  ctaEmphasis: "dominant" | "standard" | "muted";
};

/**
 * Recommended-pack Stripe checkout button on PaymentPage — Tailwind only.
 * Disabled handlers and `startCheckout` are unchanged regardless of emphasis.
 */
export function paymentRecommendedCheckoutButtonClass(
  emphasis: OrionHeroCopy["ctaEmphasis"],
): string {
  if (emphasis === "dominant") {
    return "mt-4 w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white shadow-md shadow-black/35 disabled:pointer-events-none disabled:opacity-50";
  }
  if (emphasis === "standard") {
    return "mt-4 w-full rounded-lg border border-lab-accent/50 bg-lab-accent/85 py-2.5 text-sm font-semibold text-white shadow-md shadow-black/30 disabled:pointer-events-none disabled:opacity-50";
  }
  return "mt-4 w-full rounded-lg border border-white/15 bg-white/[0.08] py-2.5 text-sm font-semibold text-lab-text shadow-sm disabled:pointer-events-none disabled:opacity-50";
}

/** ORION full contract is primary — local “what’s next” blocks should defer or shorten. */
export function orionNarrativeCoherent(
  authority: OrionAuthorityResult,
  vm: OrionViewModel,
): boolean {
  return authority.primaryNarrativeSource === "orion" && vm.fallbackMode === "full_contract";
}

/** Passive / waiting primary — avoid duplicating urgency from home summary or local CTAs. */
export function orionWaitingOrPassivePrimary(authority: OrionAuthorityResult): boolean {
  const p = authority.resolvedPrimaryRenderable;
  return (
    p.surfaceType === "passive_status" ||
    p.renderIntent === "waiting" ||
    p.renderIntent === "neutral" ||
    p.actionPresentation === "informational_only"
  );
}

const MAILING_TRACK_BTN_BASE =
  "w-full rounded-xl py-3.5 text-[15px] font-semibold transition-shadow focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none";

/** MailingPage “Continue to tracking” — visual only; `onTrack` / disabled unchanged. */
export function mailingTrackPrimaryButtonClass(emphasis: OrionHeroCopy["ctaEmphasis"]): string {
  if (emphasis === "dominant") {
    return `${MAILING_TRACK_BTN_BASE} bg-lab-accent text-white shadow-lg shadow-black/40 focus-visible:ring-lab-accent/45 disabled:bg-lab-accent/35 disabled:text-white/70 disabled:shadow-none`;
  }
  if (emphasis === "standard") {
    return `${MAILING_TRACK_BTN_BASE} border border-lab-accent/50 bg-lab-accent/85 text-white shadow-md shadow-black/30 focus-visible:ring-lab-accent/38 disabled:bg-lab-accent/35 disabled:text-white/70 disabled:shadow-none`;
  }
  return `${MAILING_TRACK_BTN_BASE} border border-white/15 bg-white/[0.08] text-lab-text shadow-sm focus-visible:ring-white/22 disabled:opacity-45 disabled:shadow-none`;
}

/** LettersReadyPage primary continue — dominant uses shared primary step token. */
export function lettersContinuePrimaryButtonClass(emphasis: OrionHeroCopy["ctaEmphasis"]): string {
  if (emphasis === "dominant") {
    return "btn-primary-step w-full disabled:!opacity-[0.45]";
  }
  if (emphasis === "standard") {
    return "w-full rounded-xl border border-lab-accent/50 bg-lab-accent/88 py-3.5 text-[15px] font-semibold text-white shadow-md shadow-black/30 disabled:pointer-events-none disabled:opacity-45";
  }
  return "w-full rounded-xl border border-white/15 bg-white/[0.08] py-3.5 text-[15px] font-semibold text-lab-text shadow-sm disabled:pointer-events-none disabled:opacity-45";
}

function actionPresentationToCtaEmphasis(
  ap: OrionPrimaryRenderable["actionPresentation"],
): OrionHeroCopy["ctaEmphasis"] {
  if (ap === "primary_cta") return "dominant";
  if (ap === "secondary_cta") return "standard";
  return "muted";
}

/**
 * Hero title/subtitle for step pages: ORION-driven when narrative source is orion, else fallbacks.
 */
export function orionStepHeroCopy(
  authority: OrionAuthorityResult,
  vm: OrionViewModel,
  fallbacks: { title: string; subtitle: string },
): OrionHeroCopy {
  if (authority.primaryNarrativeSource !== "orion") {
    return {
      title: fallbacks.title,
      subtitle: fallbacks.subtitle,
      ctaEmphasis: "standard",
    };
  }

  const p = authority.resolvedPrimaryRenderable;
  const title = primaryHeadlineFromRenderable(p) ?? fallbacks.title;

  let subtitle = fallbacks.subtitle;
  const expl = vm.bestActionExplanation;
  if (expl && typeof expl.whyNow === "string" && expl.whyNow.trim()) {
    subtitle = expl.whyNow.trim();
  } else {
    const c = p.content;
    if (c && typeof (c as { description?: unknown }).description === "string") {
      const d = String((c as { description: string }).description).trim();
      if (d) subtitle = d;
    }
  }

  return {
    title,
    subtitle,
    ctaEmphasis: actionPresentationToCtaEmphasis(p.actionPresentation),
  };
}
