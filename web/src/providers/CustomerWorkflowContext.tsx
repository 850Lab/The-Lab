import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { WorkflowIntegrityHints } from "@/lib/integrityHintsTypes";
import type { ProgramState } from "@/lib/programStateTypes";
import * as api from "@/lib/workflowApi";
import { buildOrionViewModel, type OrionViewModel } from "@/lib/orion/orionViewModel";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";
import { useAuth } from "@/providers/AuthContext";

export type CustomerWorkflowContextValue = {
  token: string;
  loading: boolean;
  error: string | null;
  workflowId: string | null;
  envelope: WorkflowEnvelope | null;
  /** Server-built program brain — sole source of step, routes, and CTA. */
  programState: ProgramState | null;
  /** Normalized ORION consumption (V1.6); use instead of ad hoc envelope field reads. */
  orionViewModel: OrionViewModel;
  canonicalCustomerPath: string;
  authoritativeStepId: string | null;
  phase: "active" | "done";
  /** Server-derived next coarse action; do not infer from local step state. */
  nextRequiredAction: WorkflowIntegrityHints["nextRequiredAction"] | null;
  integrityHints: WorkflowIntegrityHints | null;
  refresh: () => Promise<void>;
  /** Apply envelope from an API response (e.g. upload) without an extra round trip. */
  applyWorkflowEnvelope: (env: WorkflowEnvelope) => void;
  initWorkflow: () => Promise<void>;
  startStep: (stepId: string) => Promise<void>;
};

const CustomerWorkflowContext =
  createContext<CustomerWorkflowContextValue | null>(null);

export function CustomerWorkflowProvider({ children }: { children: ReactNode }) {
  const { token: authToken, emailVerified, authBootstrapping } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [envelope, setEnvelope] = useState<WorkflowEnvelope | null>(null);
  const [programState, setProgramState] = useState<ProgramState | null>(null);
  const [integrityHints, setIntegrityHints] =
    useState<WorkflowIntegrityHints | null>(null);

  const load = useCallback(async () => {
    if (authBootstrapping) return;
    const t = authToken;
    if (!t || !emailVerified) {
      setWorkflowId(null);
      setEnvelope(null);
      setProgramState(null);
      setIntegrityHints(null);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const wid = await api.fetchActiveWorkflowId(t);
      setWorkflowId(wid);
      if (wid) {
        const [env, hints, pstate] = await Promise.all([
          api.fetchWorkflowResume(t, wid),
          api.fetchWorkflowIntegrityHints(t, wid),
          api.fetchProgramState(t, wid),
        ]);
        setEnvelope(env);
        setIntegrityHints(hints);
        setProgramState(pstate);
      } else {
        setEnvelope(null);
        setProgramState(null);
        setIntegrityHints(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setWorkflowId(null);
      setEnvelope(null);
      setProgramState(null);
      setIntegrityHints(null);
    } finally {
      setLoading(false);
    }
  }, [authBootstrapping, authToken, emailVerified]);

  useEffect(() => {
    void load();
  }, [load]);

  const { authoritativeStepId, phase, canonicalCustomerPath } = useMemo(() => {
    if (programState) {
      return {
        authoritativeStepId: programState.currentStep,
        phase: programState.isComplete ? ("done" as const) : ("active" as const),
        canonicalCustomerPath: programState.canonicalRoute,
      };
    }
    return {
      authoritativeStepId: null as string | null,
      phase: "done" as const,
      canonicalCustomerPath: "/tracking",
    };
  }, [programState]);

  const nextRequiredAction = integrityHints?.nextRequiredAction ?? null;

  const orionViewModel = useMemo(
    () => buildOrionViewModel(envelope),
    [envelope],
  );

  const initWorkflow = useCallback(async () => {
    const t = authToken;
    if (!t) throw new Error("Sign in required");
    if (!emailVerified) throw new Error("Verify your email first");
    const env = await api.postWorkflowInit(t);
    const wid = env.workflowState?.workflowId;
    if (!wid || typeof wid !== "string") {
      throw new Error("Workflow init did not return an id");
    }
    setWorkflowId(wid);
    setEnvelope(env);
    setError(null);
    try {
      const [hints, pstate] = await Promise.all([
        api.fetchWorkflowIntegrityHints(t, wid),
        api.fetchProgramState(t, wid),
      ]);
      setIntegrityHints(hints);
      setProgramState(pstate);
    } catch {
      setIntegrityHints(null);
    }
  }, [authToken, emailVerified]);

  const refresh = useCallback(async () => {
    const t = authToken;
    if (!t || !workflowId) return;
    const [env, hints, pstate] = await Promise.all([
      api.fetchWorkflowResume(t, workflowId),
      api.fetchWorkflowIntegrityHints(t, workflowId),
      api.fetchProgramState(t, workflowId),
    ]);
    setEnvelope(env);
    setIntegrityHints(hints);
    setProgramState(pstate);
  }, [authToken, workflowId]);

  const startStep = useCallback(
    async (stepId: string) => {
      const t = authToken;
      if (!t || !workflowId) return;
      const env = await api.postStepStart(t, workflowId, stepId);
      setEnvelope(env);
      try {
        const [hints, pstate] = await Promise.all([
          api.fetchWorkflowIntegrityHints(t, workflowId),
          api.fetchProgramState(t, workflowId),
        ]);
        setIntegrityHints(hints);
        setProgramState(pstate);
      } catch {
        setIntegrityHints(null);
      }
    },
    [authToken, workflowId],
  );

  const applyWorkflowEnvelope = useCallback(
    (env: WorkflowEnvelope) => {
      setEnvelope(env);
      const t = authToken;
      const wid =
        (typeof env.workflowState?.workflowId === "string"
          ? env.workflowState.workflowId
          : null) ?? workflowId;
      if (t && wid) {
        void Promise.all([
          api
            .fetchWorkflowIntegrityHints(t, wid)
            .then(setIntegrityHints)
            .catch(() => setIntegrityHints(null)),
          api
            .fetchProgramState(t, wid)
            .then(setProgramState)
            .catch(() => {
              /* keep prior programState; next full refresh will reconcile */
            }),
        ]);
      }
    },
    [authToken, workflowId],
  );

  const value: CustomerWorkflowContextValue = {
    token: authToken,
    loading,
    error,
    workflowId,
    envelope,
    programState,
    orionViewModel,
    canonicalCustomerPath,
    authoritativeStepId,
    phase,
    nextRequiredAction,
    integrityHints,
    refresh,
    applyWorkflowEnvelope,
    initWorkflow,
    startStep,
  };

  return (
    <CustomerWorkflowContext.Provider value={value}>
      {children}
    </CustomerWorkflowContext.Provider>
  );
}

export function useCustomerWorkflow(): CustomerWorkflowContextValue {
  const ctx = useContext(CustomerWorkflowContext);
  if (!ctx) {
    throw new Error("useCustomerWorkflow must be used within CustomerWorkflowProvider");
  }
  return ctx;
}
