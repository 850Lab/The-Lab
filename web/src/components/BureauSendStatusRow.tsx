import { motion } from "framer-motion";
import type { ReactNode } from "react";
import type { MailBureauTruthState } from "@/lib/mailTruthTypes";

export type BureauSendRowProps = {
  bureauDisplay: string;
  mailRowState: MailBureauTruthState;
  isTestSend: boolean;
  lobId?: string;
  lobErrorMessageSafe?: string;
  trackingNumber?: string;
  trackingUrl?: string;
  expectedDelivery?: string;
  actionSlot?: ReactNode;
};

function rowHeadline(
  mailRowState: MailBureauTruthState,
): { label: string; tone: "muted" | "amber" | "sky" | "red" | "emerald" } {
  switch (mailRowState) {
    case "pending":
      return { label: "Not submitted", tone: "muted" };
    case "processing":
      return { label: "Submitted — processing", tone: "sky" };
    case "sending_failed":
      return { label: "Send failed", tone: "red" };
    case "sent_test":
      return { label: "Test — no USPS mail", tone: "amber" };
    case "sent_live":
      return { label: "Live — submitted (tracking may be pending)", tone: "sky" };
    case "tracking_available":
      return { label: "Live — tracking active", tone: "emerald" };
    default:
      return { label: "Unknown", tone: "muted" };
  }
}

function toneClasses(tone: ReturnType<typeof rowHeadline>["tone"]): string {
  switch (tone) {
    case "amber":
      return "bg-amber-500/12 text-amber-300/95";
    case "sky":
      return "bg-sky-500/12 text-sky-200/95";
    case "red":
      return "bg-red-500/12 text-red-200/95";
    case "emerald":
      return "bg-emerald-500/12 text-emerald-300/95";
    default:
      return "bg-white/[0.06] text-lab-muted";
  }
}

export function BureauSendStatusRow({
  bureauDisplay,
  mailRowState,
  isTestSend,
  lobId,
  lobErrorMessageSafe,
  trackingNumber,
  trackingUrl,
  expectedDelivery,
  actionSlot,
}: BureauSendRowProps) {
  const { label, tone } = rowHeadline(mailRowState);
  const showProcessorDetail =
    mailRowState !== "pending" &&
    mailRowState !== "sending_failed" &&
    Boolean(lobId?.trim());

  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 10 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className="flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-3.5 sm:px-5 sm:py-4"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span
            className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${toneClasses(tone)}`}
            aria-hidden
          >
            {mailRowState === "tracking_available" ? (
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.25}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            ) : mailRowState === "sending_failed" ? (
              <span className="text-sm font-bold">!</span>
            ) : (
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            )}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[15px] font-medium text-lab-text sm:text-base">
              {bureauDisplay}
            </p>
            {isTestSend && mailRowState !== "pending" ? (
              <p className="mt-0.5 text-xs text-amber-200/85">Lob test mode</p>
            ) : null}
            {trackingNumber && mailRowState !== "sent_test" ? (
              <p className="mt-0.5 text-xs text-lab-subtle">USPS tracking {trackingNumber}</p>
            ) : null}
            {expectedDelivery && mailRowState === "tracking_available" ? (
              <p className="text-xs text-lab-muted">
                Est. delivery (processor estimate, not guaranteed): {expectedDelivery}
              </p>
            ) : null}
            {mailRowState === "sending_failed" && lobErrorMessageSafe ? (
              <p className="mt-1 text-xs text-red-200/90">{lobErrorMessageSafe}</p>
            ) : null}
          </div>
        </div>
        <span
          className={`shrink-0 text-right text-xs font-medium leading-snug sm:text-sm ${
            tone === "muted" ? "text-lab-muted" : "text-lab-text"
          }`}
        >
          {label}
        </span>
      </div>
      {showProcessorDetail ? (
        <p className="text-xs text-lab-subtle">
          Processor reference (Lob):{" "}
          <span className="font-mono text-lab-muted">{lobId}</span>
        </p>
      ) : null}
      {trackingUrl && mailRowState !== "sent_test" ? (
        <a
          href={trackingUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-lab-accent hover:underline"
        >
          Open USPS tracking
        </a>
      ) : null}
      {actionSlot ? <div className="pt-1">{actionSlot}</div> : null}
    </motion.div>
  );
}
