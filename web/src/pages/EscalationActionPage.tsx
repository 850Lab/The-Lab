import { useEffect } from "react";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { setWorkflowStep } from "@/lib/workflow";

export function EscalationActionPage() {
  useEffect(() => {
    setWorkflowStep("escalation_action");
  }, []);

  return (
    <div className="min-h-full bg-lab-bg">
      <TopBarMinimal />
      <main className="mx-auto max-w-md px-4 pb-16 pt-24 sm:px-6 sm:pt-28">
        <h1 className="text-2xl font-semibold text-lab-text">Next action</h1>
        <p className="mt-3 text-sm leading-relaxed text-lab-muted">
          Your prepared escalation will appear here. Connect this route to your
          letter or complaint flow.
        </p>
      </main>
    </div>
  );
}
