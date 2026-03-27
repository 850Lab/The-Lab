import { useMemo } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  customerPathForNextRequiredAction,
  isEscalationPath,
} from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

type BannerSpec = {
  title: string;
  body: string;
  ctaLabel: string;
};

function pickBanner(
  h: NonNullable<ReturnType<typeof useCustomerWorkflow>["integrityHints"]>,
): BannerSpec | null {
  if (h.workflowStepMismatch) {
    return {
      title: "We’ve moved you to the correct step",
      body: "Your workflow position was out of sync; use the button below to continue where you should be.",
      ctaLabel: "Go to current step",
    };
  }
  if (h.entitlementsButPaymentIncomplete) {
    return {
      title: "Finish activating your purchase",
      body: "Your letter credits are ready, but this step still needs to be completed so the workflow can continue.",
      ctaLabel: "Continue",
    };
  }
  if (h.paymentCompletedButWrongStep) {
    return {
      title: "Payment is complete",
      body: "Continue from your current workflow step when you’re ready.",
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
      body: "A mailing credit was used without a matching mailed record. If this persists, contact support with your workflow id.",
      ctaLabel: "Continue",
    };
  }
  return null;
}

/**
 * One primary system banner from GET /integrity-hints (backend truth only).
 */
export function WorkflowIntegrityBanner() {
  const loc = useLocation();
  const {
    loading,
    workflowId,
    integrityHints,
    canonicalCustomerPath,
    nextRequiredAction,
  } = useCustomerWorkflow();

  const spec = useMemo(() => {
    if (!integrityHints) return null;
    return pickBanner(integrityHints);
  }, [integrityHints]);

  const ctaPath = useMemo(() => {
    if (!integrityHints || !nextRequiredAction) return canonicalCustomerPath;
    return customerPathForNextRequiredAction(
      nextRequiredAction,
      canonicalCustomerPath,
    );
  }, [integrityHints, nextRequiredAction, canonicalCustomerPath]);

  if (loading || !workflowId || !spec) return null;
  if (isEscalationPath(loc.pathname)) return null;

  return (
    <div
      className="border-b border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-50"
      role="status"
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-medium text-amber-100">{spec.title}</p>
          <p className="mt-0.5 text-amber-100/80">{spec.body}</p>
        </div>
        <Link
          to={ctaPath}
          className="shrink-0 rounded-md bg-amber-500/90 px-3 py-1.5 text-center font-medium text-slate-950 hover:bg-amber-400"
        >
          {spec.ctaLabel}
        </Link>
      </div>
    </div>
  );
}
