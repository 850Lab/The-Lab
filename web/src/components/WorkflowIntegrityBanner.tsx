import { useMemo } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  pickIntegrityBannerSpec,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import {
  customerPathForNextRequiredAction,
  isEscalationPath,
  isOrgProgramPath,
} from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

/**
 * Integrity constraints from GET /integrity-hints. When ORION full_contract already states the same
 * next move as a soft integrity hint, the coordinator suppresses this banner to avoid dueling narratives.
 */
export function WorkflowIntegrityBanner() {
  const loc = useLocation();
  const {
    loading,
    workflowId,
    programState,
    integrityHints,
    canonicalCustomerPath,
    nextRequiredAction,
    orionViewModel,
  } = useCustomerWorkflow();

  const authority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const spec = useMemo(() => {
    if (authority.shouldSuppressIntegrityBanner) return null;
    return pickIntegrityBannerSpec(integrityHints);
  }, [authority.shouldSuppressIntegrityBanner, integrityHints]);

  const ctaPath = useMemo(() => {
    if (programState?.nextBestAction?.targetRoute) {
      return programState.nextBestAction.targetRoute;
    }
    if (!integrityHints) return canonicalCustomerPath;
    if (integrityHints.mailBlocked && nextRequiredAction === "mail") {
      return "/tracking";
    }
    if (!nextRequiredAction) return canonicalCustomerPath;
    return customerPathForNextRequiredAction(
      nextRequiredAction,
      canonicalCustomerPath,
    );
  }, [
    programState,
    integrityHints,
    nextRequiredAction,
    canonicalCustomerPath,
  ]);

  if (loading || !workflowId || !spec) return null;
  if (isEscalationPath(loc.pathname)) return null;
  if (isOrgProgramPath(loc.pathname)) return null;

  return (
    <div className="pt-14">
      <div
        className="border-b border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-50"
        role="status"
        data-integrity-banner="active"
      >
        <div className="mx-auto flex max-w-3xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-medium text-amber-100">{spec.title}</p>
            <p className="mt-0.5 text-amber-100/80">{spec.body}</p>
          </div>
          <Link
            to={ctaPath}
            className="shrink-0 rounded-md bg-amber-500/90 px-3 py-1.5 text-center font-medium text-zinc-950 hover:bg-amber-400"
          >
            {spec.ctaLabel}
          </Link>
        </div>
      </div>
    </div>
  );
}
