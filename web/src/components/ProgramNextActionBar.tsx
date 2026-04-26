import { Link, useLocation } from "react-router-dom";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

/**
 * **Recovery / navigation** from `ProgramState.nextBestAction` when the user is off the
 * server’s target route (e.g. mail blocked → open tracking). It is not a substitute for
 * step forms or submit buttons; those stay the real primary action on the current page.
 * Hidden when `pathname` already matches `nextBestAction.targetRoute`.
 */
export function ProgramNextActionBar() {
  const { programState, workflowId } = useCustomerWorkflow();
  const loc = useLocation();
  if (!workflowId || !programState?.nextBestAction?.required) return null;
  const n = programState.nextBestAction;
  if (loc.pathname === n.targetRoute) return null;
  return (
    <div className="mt-8 border-t border-white/10 pt-4" data-program-brain-cta>
      <div className="flex flex-col items-center gap-1">
        <p className="text-center text-xs text-lab-subtle">Next in your program</p>
        <Link
          to={n.targetRoute}
          className="inline-flex min-h-[2.5rem] items-center justify-center rounded-md bg-lab-accent px-5 text-sm font-semibold text-zinc-950 hover:brightness-110"
        >
          {n.label}
        </Link>
      </div>
    </div>
  );
}
