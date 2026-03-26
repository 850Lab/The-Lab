import { useEffect, useState } from "react";
import { formatMccErrorMessage } from "@/lib/missionControlApi";
import { McOperatorFields } from "@/components/mission-control/McOperatorFields";

const DEFAULT_ACTOR = "mission_control_ui";

type AuditPayload = { actor_source: string; reason_safe: string };

type Props = {
  open: boolean;
  title: string;
  confirmLabel?: string;
  /** When true, actor_source and reason_safe must be non-empty before running. */
  requireAuditFields: boolean;
  onClose: () => void;
  onRun: (audit: AuditPayload | null) => Promise<void>;
  children?: React.ReactNode;
};

export function McActionModal({
  open,
  title,
  confirmLabel = "Confirm",
  requireAuditFields,
  onClose,
  onRun,
  children,
}: Props) {
  const [actorSource, setActorSource] = useState(DEFAULT_ACTOR);
  const [reasonSafe, setReasonSafe] = useState("");
  const [busy, setBusy] = useState(false);
  const [localErr, setLocalErr] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setLocalErr(null);
      setBusy(false);
      if (requireAuditFields) setReasonSafe("");
    }
  }, [open, requireAuditFields]);

  if (!open) return null;

  const run = async () => {
    setLocalErr(null);
    let audit: AuditPayload | null = null;
    if (requireAuditFields) {
      const a = actorSource.trim();
      const r = reasonSafe.trim();
      if (!a || !r) {
        setLocalErr("actor_source and reason_safe are required.");
        return;
      }
      audit = { actor_source: a, reason_safe: r };
    }
    setBusy(true);
    try {
      await onRun(audit);
      onClose();
    } catch (e) {
      setLocalErr(formatMccErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 p-4">
      <div
        className="w-full max-w-lg rounded-lg border border-white/15 bg-lab-surface p-4 shadow-xl space-y-3"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mc-action-title"
      >
        <h4 id="mc-action-title" className="text-sm font-semibold text-lab-text">
          {title}
        </h4>
        {children}
        {requireAuditFields ? (
          <McOperatorFields
            actorSource={actorSource}
            reasonSafe={reasonSafe}
            onActorSource={setActorSource}
            onReasonSafe={setReasonSafe}
            disabled={busy}
          />
        ) : null}
        {localErr ? (
          <p className="text-xs text-red-300 whitespace-pre-wrap">{localErr}</p>
        ) : null}
        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            className="rounded border border-white/20 px-3 py-1.5 text-sm text-lab-muted hover:bg-white/5"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="rounded bg-lab-accent/90 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            onClick={run}
            disabled={busy}
          >
            {busy ? "…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
