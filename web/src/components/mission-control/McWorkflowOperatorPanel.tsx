import { useEffect, useMemo, useState } from "react";
import { McActionModal } from "@/components/mission-control/McActionModal";
import { McResponseOverrideDialogs } from "@/components/mission-control/McResponseOverrideDialogs";
import type { ResponseOverrideOp } from "@/components/mission-control/McResponseOverrideDialogs";
import {
  adminClearStalled,
  adminCreateReminderCandidatesMc,
  adminDeliverReminderMc,
  adminPaymentWaived,
  adminQueueReminderMc,
  adminRecoveryMailRetry,
  adminRecoveryResumeCurrent,
  adminRecoveryRetryStep,
  adminReopenStep,
  adminSkipReminder,
} from "@/lib/missionControlApi";

type Props = {
  workflowId: string;
  userId: number;
  homeSummary: Record<string, unknown>;
  responsesForActions: Record<string, unknown>[];
  onRefresh: () => Promise<void>;
};

export function McWorkflowOperatorPanel({
  workflowId,
  userId,
  homeSummary: hs,
  responsesForActions,
  onRefresh,
}: Props) {
  const failedStep = hs.failedStep as Record<string, unknown> | null | undefined;
  const defaultStepId =
    typeof failedStep?.stepId === "string" ? failedStep.stepId : "";
  const stalled = Boolean(hs.stalled);
  const recoveryActions =
    (hs.recoveryActions as Record<string, unknown>[]) || [];
  const activeReminders =
    (hs.activeReminders as Record<string, unknown>[]) || [];
  const currentStepId =
    typeof hs.currentStepId === "string" ? hs.currentStepId : "";

  const retryStepActions = useMemo(
    () =>
      recoveryActions.filter(
        (a) => a.actionType === "retry_step" && typeof a.stepId === "string",
      ),
    [recoveryActions],
  );
  const canResume = recoveryActions.some(
    (a) => a.actionType === "resume_current_step",
  );
  const canMail = recoveryActions.some(
    (a) => a.actionType === "re_run_mail_attempt",
  );

  type Modal =
    | null
    | "reopen"
    | "waive"
    | "clearStalled"
    | "recoveryRetry"
    | "recoveryResume"
    | "mailRetry"
    | "reminderCandidates"
    | "skipRem"
    | "queueRem"
    | "deliverRem";

  const [modal, setModal] = useState<Modal>(null);
  const [stepIdDraft, setStepIdDraft] = useState(defaultStepId);
  const [retryStepId, setRetryStepId] = useState(
    (retryStepActions[0]?.stepId as string) || defaultStepId,
  );
  const [remTargetId, setRemTargetId] = useState<string | null>(null);
  const [overrideOp, setOverrideOp] = useState<ResponseOverrideOp>(null);

  useEffect(() => {
    setStepIdDraft(defaultStepId);
    setRetryStepId(
      (retryStepActions[0]?.stepId as string) || defaultStepId,
    );
  }, [defaultStepId, retryStepActions]);

  const btnClass =
    "rounded border border-white/20 bg-lab-elevated px-2 py-1 text-xs text-lab-text hover:bg-white/10";

  return (
    <section id="operator-actions" className="space-y-3">
      <h3 className="text-sm font-semibold text-lab-muted">
        Operator actions
      </h3>
      <p className="text-xs text-lab-subtle max-w-3xl">
        Each action calls an existing admin API. Confirm in the modal; after
        success, detail data is reloaded from the server.
      </p>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={btnClass}
          onClick={() => setModal("reopen")}
        >
          Reopen step
        </button>
        <button
          type="button"
          className={btnClass}
          onClick={() => setModal("waive")}
        >
          Waive payment
        </button>
        {stalled ? (
          <button
            type="button"
            className={btnClass}
            onClick={() => setModal("clearStalled")}
          >
            Clear stalled flag
          </button>
        ) : null}
        {retryStepActions.length > 0 ? (
          <button
            type="button"
            className={btnClass}
            onClick={() => setModal("recoveryRetry")}
          >
            Recovery: retry step
          </button>
        ) : null}
        {canResume ? (
          <button
            type="button"
            className={btnClass}
            onClick={() => setModal("recoveryResume")}
          >
            Recovery: resume current step
          </button>
        ) : null}
        {canMail ? (
          <button
            type="button"
            className={btnClass}
            onClick={() => setModal("mailRetry")}
          >
            Recovery: re-run mail attempt
          </button>
        ) : null}
        <button
          type="button"
          className={btnClass}
          onClick={() => setModal("reminderCandidates")}
        >
          Create reminder candidates
        </button>
      </div>

      {activeReminders.length > 0 ? (
        <div className="rounded border border-white/10 p-3 space-y-2">
          <h4 className="text-xs font-semibold text-lab-muted">
            Active reminders (eligible / queued)
          </h4>
          <ul className="space-y-2 text-xs">
            {activeReminders.map((r) => {
              const id = String(r.reminder_id ?? "");
              const st = String(r.status ?? "");
              return (
                <li
                  key={id}
                  className="flex flex-wrap items-center gap-2 border-b border-white/5 pb-2"
                >
                  <span className="font-mono text-lab-subtle">{id}</span>
                  <span className="text-lab-muted">{st}</span>
                  {st !== "sent" ? (
                    <button
                      type="button"
                      className="text-sky-300 hover:underline"
                      onClick={() => {
                        setRemTargetId(id);
                        setModal("skipRem");
                      }}
                    >
                      Skip
                    </button>
                  ) : null}
                  {st === "eligible" ? (
                    <button
                      type="button"
                      className="text-sky-300 hover:underline"
                      onClick={() => {
                        setRemTargetId(id);
                        setModal("queueRem");
                      }}
                    >
                      Queue
                    </button>
                  ) : null}
                  {st === "queued" ? (
                    <button
                      type="button"
                      className="text-sky-300 hover:underline"
                      onClick={() => {
                        setRemTargetId(id);
                        setModal("deliverRem");
                      }}
                    >
                      Deliver
                    </button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      {responsesForActions.length > 0 ? (
        <div className="overflow-x-auto rounded border border-white/10">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-white/10 bg-lab-surface text-lab-muted">
                <th className="p-2">Response</th>
                <th className="p-2">Classification</th>
                <th className="p-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {responsesForActions.map((r) => {
                const rid = String(r.response_id ?? "");
                return (
                  <tr key={rid} className="border-b border-white/5">
                    <td className="p-2 font-mono">{rid.slice(0, 8)}…</td>
                    <td className="p-2 max-w-xs truncate">
                      {String(
                        r.response_classification ??
                          r.classification_status ??
                          "—",
                      )}
                    </td>
                    <td className="p-2 space-x-2 whitespace-nowrap">
                      <button
                        type="button"
                        className="text-sky-300 hover:underline"
                        onClick={() =>
                          setOverrideOp({ type: "classification", row: r })
                        }
                      >
                        Override class
                      </button>
                      <button
                        type="button"
                        className="text-sky-300 hover:underline"
                        onClick={() =>
                          setOverrideOp({ type: "escalation", row: r })
                        }
                      >
                        Override escalation
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <McActionModal
        open={modal === "reopen"}
        title="Reopen failed step"
        requireAuditFields
        onClose={() => setModal(null)}
        onRun={async (op) => {
          const sid = stepIdDraft.trim();
          if (!sid) throw new Error("step_id is required.");
          await adminReopenStep(workflowId, { ...op!, step_id: sid });
          await onRefresh();
        }}
      >
        <label className="block text-xs text-lab-muted">
          step_id
          <input
            className="mt-1 w-full rounded border border-white/15 bg-lab-elevated px-2 py-1 font-mono text-xs text-lab-text"
            value={stepIdDraft}
            onChange={(e) => setStepIdDraft(e.target.value)}
          />
        </label>
        {currentStepId ? (
          <p className="text-xs text-lab-subtle">
            Current step hint:{" "}
            <span className="font-mono">{currentStepId}</span>
          </p>
        ) : null}
      </McActionModal>

      <McActionModal
        open={modal === "waive"}
        title="Mark payment waived"
        requireAuditFields
        onClose={() => setModal(null)}
        onRun={async (op) => {
          await adminPaymentWaived(workflowId, op!);
          await onRefresh();
        }}
      />

      <McActionModal
        open={modal === "clearStalled"}
        title="Clear stalled flag"
        requireAuditFields
        onClose={() => setModal(null)}
        onRun={async (op) => {
          await adminClearStalled(workflowId, op!);
          await onRefresh();
        }}
      />

      <McActionModal
        open={modal === "recoveryRetry"}
        title="Recovery: retry failed step (engine)"
        requireAuditFields
        onClose={() => setModal(null)}
        onRun={async (op) => {
          const sid = retryStepId.trim();
          if (!sid) throw new Error("step_id is required.");
          await adminRecoveryRetryStep(workflowId, {
            ...op!,
            user_id: userId,
            step_id: sid,
          });
          await onRefresh();
        }}
      >
        <label className="block text-xs text-lab-muted">
          step_id
          <input
            className="mt-1 w-full rounded border border-white/15 bg-lab-elevated px-2 py-1 font-mono text-xs text-lab-text"
            value={retryStepId}
            onChange={(e) => setRetryStepId(e.target.value)}
          />
        </label>
      </McActionModal>

      <McActionModal
        open={modal === "recoveryResume"}
        title="Recovery: resume current step (start_step)"
        requireAuditFields
        onClose={() => setModal(null)}
        onRun={async (op) => {
          await adminRecoveryResumeCurrent(workflowId, {
            ...op!,
            user_id: userId,
          });
          await onRefresh();
        }}
      />

      <McActionModal
        open={modal === "mailRetry"}
        title="Recovery: re-run mail attempt"
        requireAuditFields
        onClose={() => setModal(null)}
        onRun={async (op) => {
          await adminRecoveryMailRetry(workflowId, {
            ...op!,
            user_id: userId,
          });
          await onRefresh();
        }}
      />

      <McActionModal
        open={modal === "reminderCandidates"}
        title="Create reminder candidates from eligibility"
        confirmLabel="Create candidates"
        requireAuditFields={false}
        onClose={() => setModal(null)}
        onRun={async () => {
          await adminCreateReminderCandidatesMc(workflowId);
          await onRefresh();
        }}
      >
        <p className="text-xs text-lab-subtle">
          Inserts eligible reminder rows when home-summary flags allow and
          dedup rules pass.
        </p>
      </McActionModal>

      <McActionModal
        open={modal === "skipRem" && !!remTargetId}
        title="Skip reminder"
        requireAuditFields
        onClose={() => {
          setModal(null);
          setRemTargetId(null);
        }}
        onRun={async (op) => {
          await adminSkipReminder(remTargetId!, op!);
          setRemTargetId(null);
          await onRefresh();
        }}
      />

      <McActionModal
        open={modal === "queueRem" && !!remTargetId}
        title="Queue reminder for delivery"
        confirmLabel="Queue"
        requireAuditFields={false}
        onClose={() => {
          setModal(null);
          setRemTargetId(null);
        }}
        onRun={async () => {
          await adminQueueReminderMc(remTargetId!);
          setRemTargetId(null);
          await onRefresh();
        }}
      />

      <McActionModal
        open={modal === "deliverRem" && !!remTargetId}
        title="Deliver queued reminder now"
        confirmLabel="Deliver"
        requireAuditFields={false}
        onClose={() => {
          setModal(null);
          setRemTargetId(null);
        }}
        onRun={async () => {
          await adminDeliverReminderMc(remTargetId!);
          setRemTargetId(null);
          await onRefresh();
        }}
      >
        <p className="text-xs text-amber-200/90">
          Runs real delivery for queued reminders (email/SMS routing per
          backend).
        </p>
      </McActionModal>

      <McResponseOverrideDialogs
        op={overrideOp}
        onClose={() => setOverrideOp(null)}
        onSuccess={async () => {
          setOverrideOp(null);
          await onRefresh();
        }}
      />
    </section>
  );
}
