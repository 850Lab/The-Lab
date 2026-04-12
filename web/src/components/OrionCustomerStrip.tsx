import { useMemo } from "react";
import { useLocation } from "react-router-dom";
import {
  isEscalationPath,
  isOrgProgramPath,
} from "@/lib/workflowStepRoutes";
import { hintForPrimarySurface, primaryHeadlineFromRenderable, supportingHeadlineFromContent } from "@/lib/orion/orionSurfaceProps";
import {
  resolvePrimaryRenderable,
  resolveSupportingRenderables,
} from "@/lib/orion/orionViewModel";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

/**
 * Single shared ORION consumption surface for customer workflow routes.
 * Honors backend `uxSurfaceContract` / prioritization via normalized view model (no local re-ranking).
 */
export function OrionCustomerStrip() {
  const loc = useLocation();
  const { loading, workflowId, orionViewModel: vm } = useCustomerWorkflow();

  const primary = useMemo(() => resolvePrimaryRenderable(vm), [vm]);
  const supporting = useMemo(() => resolveSupportingRenderables(vm), [vm]);

  const headline = useMemo(() => primaryHeadlineFromRenderable(primary), [primary]);
  const hint = useMemo(
    () => hintForPrimarySurface(primary.surfaceType, primary.renderIntent),
    [primary.surfaceType, primary.renderIntent],
  );

  if (loading || !workflowId) return null;
  if (!vm.hasOrion || vm.fallbackMode === "legacy_fallback") return null;
  if (isEscalationPath(loc.pathname) || isOrgProgramPath(loc.pathname)) return null;
  if (!headline && supporting.length === 0) return null;

  const toneBorder =
    hint.tone === "amber"
      ? "border-amber-500/35 bg-amber-500/[0.07]"
      : hint.tone === "emerald"
        ? "border-emerald-500/30 bg-emerald-500/[0.06]"
        : "border-white/[0.08] bg-black/20";

  return (
    <div className="border-b px-4 py-2.5 text-sm text-lab-muted" data-orion-fallback={vm.fallbackMode}>
      <div className={`mx-auto max-w-3xl rounded-lg border ${toneBorder} px-3 py-2`}>
        {headline ? (
          <p className={`font-medium ${hint.emphasis === "high" ? "text-lab-text" : "text-lab-muted"}`}>
            {headline}
          </p>
        ) : null}
        {supporting.map((s, i) => {
          const sub = supportingHeadlineFromContent(s.content);
          if (!sub) return null;
          return (
            <p key={i} className="mt-1 text-xs leading-snug text-lab-subtle">
              {sub}
            </p>
          );
        })}
      </div>
    </div>
  );
}
