const STORAGE_KEY = "850lab_workflow_v1";

export type WorkflowStep =
  | "upload"
  | "analyze"
  | "prepare"
  | "strategy"
  | "payment"
  | "letters"
  | "proof"
  | "send"
  | "tracking"
  | "escalation"
  | "escalation_action";

export type WorkflowState = {
  step: WorkflowStep;
  updatedAt?: number;
};

export function getWorkflowState(): WorkflowState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as WorkflowState;
    if (parsed?.step) return parsed;
  } catch {
    /* ignore */
  }
  return null;
}

export function setWorkflowStep(step: WorkflowStep): void {
  const next: WorkflowState = { step, updatedAt: Date.now() };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

export function pathForStep(step: WorkflowStep): string {
  const paths: Record<WorkflowStep, string> = {
    upload: "/upload",
    analyze: "/analyze",
    prepare: "/prepare",
    strategy: "/strategy",
    payment: "/payment",
    letters: "/letters",
    proof: "/proof",
    send: "/send",
    tracking: "/tracking",
    escalation: "/escalation",
    escalation_action: "/escalation-action",
  };
  return paths[step];
}
