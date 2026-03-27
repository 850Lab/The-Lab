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
import * as api from "@/lib/workflowApi";
import {
  computeAuthoritativeStep,
  customerRouteForBackendStep,
} from "@/lib/workflowStepRoutes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";
import { useAuth } from "@/providers/AuthContext";

export type CustomerWorkflowContextValue = {
  token: string;
  loading: boolean;
  error: string | null;
  workflowId: string | null;
  envelope: WorkflowEnvelope | null;
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
  const [integrityHints, setIntegrityHints] =
    useState<WorkflowIntegrityHints | null>(null);

  const load = useCallback(async () => {
    if (authBootstrapping) return;
    const t = authToken;
    if (!t || !emailVerified) {
      setWorkflowId(null);
      setEnvelope(null);
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
        const [env, hints] = await Promise.all([
          api.fetchWorkflowResume(t, wid),
          api.fetchWorkflowIntegrityHints(t, wid),
        ]);
        setEnvelope(env);
        setIntegrityHints(hints);
      } else {
        setEnvelope(null);
        setIntegrityHints(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setWorkflowId(null);
      setEnvelope(null);
      setIntegrityHints(null);
    } finally {
      setLoading(false);
    }
  }, [authBootstrapping, authToken, emailVerified]);

  useEffect(() => {
    void load();
  }, [load]);

  const { authoritativeStepId, phase, canonicalCustomerPath } = useMemo(() => {
    if (!envelope?.stepStatus?.length) {
      return {
        authoritativeStepId: null as string | null,
        phase: "done" as const,
        canonicalCustomerPath: "/tracking",
      };
    }
    const a = computeAuthoritativeStep(envelope.stepStatus);
    return {
      authoritativeStepId: a.stepId,
      phase: a.phase,
      canonicalCustomerPath: customerRouteForBackendStep(a.stepId, a.phase),
    };
  }, [envelope]);

  const nextRequiredAction = integrityHints?.nextRequiredAction ?? null;

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
      const hints = await api.fetchWorkflowIntegrityHints(t, wid);
      setIntegrityHints(hints);
    } catch {
      setIntegrityHints(null);
    }
  }, [authToken, emailVerified]);

  const refresh = useCallback(async () => {
    const t = authToken;
    if (!t || !workflowId) return;
    const [env, hints] = await Promise.all([
      api.fetchWorkflowResume(t, workflowId),
      api.fetchWorkflowIntegrityHints(t, workflowId),
    ]);
    setEnvelope(env);
    setIntegrityHints(hints);
  }, [authToken, workflowId]);

  const startStep = useCallback(
    async (stepId: string) => {
      const t = authToken;
      if (!t || !workflowId) return;
      const env = await api.postStepStart(t, workflowId, stepId);
      setEnvelope(env);
      try {
        const hints = await api.fetchWorkflowIntegrityHints(t, workflowId);
        setIntegrityHints(hints);
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
        void api
          .fetchWorkflowIntegrityHints(t, wid)
          .then(setIntegrityHints)
          .catch(() => setIntegrityHints(null));
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
