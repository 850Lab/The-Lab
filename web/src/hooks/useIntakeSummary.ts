import { useCallback, useEffect, useRef, useState } from "react";
import { fetchIntakeSummary } from "@/lib/workflowApi";
import type { IntakeSummaryBundle } from "@/lib/intakeTypes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const POLL_MS = 2500;

export function useIntakeSummary() {
  const { token, workflowId, envelope, authoritativeStepId, applyWorkflowEnvelope } =
    useCustomerWorkflow();
  const [bundle, setBundle] = useState<IntakeSummaryBundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const parseRow = envelope?.stepStatus?.find((s) => s.stepId === "parse_analyze");
  const parseDone = parseRow?.status === "completed" || parseRow?.status === "failed";
  const shouldPollParse =
    authoritativeStepId === "parse_analyze" &&
    !!parseRow &&
    !parseDone;

  const load = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!token || !workflowId) {
        setBundle(null);
        setLoading(false);
        setError(null);
        return;
      }
      if (!opts?.silent) {
        setLoading(true);
        setError(null);
      }
      try {
        const b = await fetchIntakeSummary(token, workflowId);
        setBundle(b);
        applyWorkflowEnvelope(b.workflow);
        setError(null);
      } catch (e) {
        if (!opts?.silent) {
          setError(e instanceof Error ? e.message : String(e));
          setBundle(null);
        }
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [token, workflowId, applyWorkflowEnvelope],
  );

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (!shouldPollParse || !token || !workflowId) return;
    timerRef.current = setInterval(() => {
      void load({ silent: true });
    }, POLL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [shouldPollParse, token, workflowId, load]);

  return { bundle, loading, error, reload: load };
}
