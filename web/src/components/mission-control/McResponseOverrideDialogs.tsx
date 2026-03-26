import { useEffect, useState } from "react";
import { McActionModal } from "@/components/mission-control/McActionModal";
import {
  adminOverrideClassification,
  adminOverrideEscalation,
} from "@/lib/missionControlApi";

type Row = Record<string, unknown>;

export type ResponseOverrideOp =
  | null
  | { type: "classification"; row: Row }
  | { type: "escalation"; row: Row };

type Props = {
  op: ResponseOverrideOp;
  onClose: () => void;
  onSuccess: () => Promise<void>;
};

export function McResponseOverrideDialogs({ op, onClose, onSuccess }: Props) {
  const [newClassification, setNewClassification] = useState("");
  const [classificationReasoning, setClassificationReasoning] = useState("");
  const [escalationJson, setEscalationJson] = useState("{}");

  useEffect(() => {
    if (op?.type === "classification") {
      setNewClassification("");
      setClassificationReasoning("");
    }
    if (op?.type === "escalation") {
      const er = op.row.escalation_recommendation;
      setEscalationJson(
        JSON.stringify(er && typeof er === "object" ? er : {}, null, 2),
      );
    }
  }, [op]);

  return (
    <>
      <McActionModal
        open={op?.type === "classification"}
        title="Override response classification"
        requireAuditFields
        onClose={onClose}
        onRun={async (audit) => {
          const nc = newClassification.trim();
          if (!nc) throw new Error("new_classification is required.");
          await adminOverrideClassification({
            response_id: String(op!.row.response_id),
            new_classification: nc,
            reasoning_safe: classificationReasoning.trim(),
            actor_source: audit!.actor_source,
            reason_safe: audit!.reason_safe,
          });
          await onSuccess();
        }}
      >
        <label className="block text-xs text-lab-muted">
          new_classification
          <input
            className="mt-1 w-full rounded border border-white/15 bg-lab-elevated px-2 py-1 font-mono text-xs text-lab-text"
            value={newClassification}
            onChange={(e) => setNewClassification(e.target.value)}
          />
        </label>
        <label className="block text-xs text-lab-muted mt-2">
          reasoning_safe (optional)
          <input
            className="mt-1 w-full rounded border border-white/15 bg-lab-elevated px-2 py-1 text-xs text-lab-text"
            value={classificationReasoning}
            onChange={(e) => setClassificationReasoning(e.target.value)}
          />
        </label>
      </McActionModal>

      <McActionModal
        open={op?.type === "escalation"}
        title="Override escalation recommendation (JSON object)"
        requireAuditFields
        onClose={onClose}
        onRun={async (audit) => {
          let obj: Record<string, unknown> = {};
          try {
            const p = JSON.parse(escalationJson) as unknown;
            if (p && typeof p === "object" && !Array.isArray(p))
              obj = p as Record<string, unknown>;
            else throw new Error("Payload must be a JSON object.");
          } catch {
            throw new Error("Invalid JSON for escalation_recommendation.");
          }
          await adminOverrideEscalation({
            response_id: String(op!.row.response_id),
            escalation_recommendation: obj,
            actor_source: audit!.actor_source,
            reason_safe: audit!.reason_safe,
          });
          await onSuccess();
        }}
      >
        <label className="block text-xs text-lab-muted">
          escalation_recommendation
          <textarea
            className="mt-1 w-full min-h-[100px] rounded border border-white/15 bg-lab-elevated px-2 py-1 font-mono text-xs text-lab-text"
            value={escalationJson}
            onChange={(e) => setEscalationJson(e.target.value)}
          />
        </label>
      </McActionModal>
    </>
  );
}
