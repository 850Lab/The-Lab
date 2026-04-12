import { motion } from "framer-motion";

type Props = {
  bureau: string;
  status: string;
  onViewDetails: () => void;
};

/** Shorter labels for badges; full status kept for accessibility. */
function friendlyStatusLabel(s: string): string {
  const m: Record<string, string> = {
    "Submitted — tracking active": "In transit",
    "Submitted — tracking pending": "Tracking pending",
    Processing: "Processing",
    "Test — no USPS mail": "Test (no USPS mail)",
    "Send failed": "Send failed",
    "Not submitted": "Not mailed yet",
  };
  return m[s] ?? s;
}

function statusTone(s: string): string {
  switch (s) {
    case "Submitted — tracking active":
      return "text-emerald-300/95 bg-emerald-500/12";
    case "Submitted — tracking pending":
    case "Processing":
      return "text-zinc-300/95 bg-zinc-500/15";
    case "Test — no USPS mail":
      return "text-amber-200/95 bg-amber-500/12";
    case "Send failed":
      return "text-red-200/95 bg-red-500/12";
    case "Not submitted":
      return "text-lab-muted bg-white/[0.06]";
    default:
      return "text-lab-muted bg-white/[0.06]";
  }
}

export function BureauTrackingRow({ bureau, status, onViewDetails }: Props) {
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
      className="flex flex-col gap-3 rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5 sm:py-4"
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2 sm:gap-3">
        <span className="text-[15px] font-semibold text-lab-text sm:text-base">
          {bureau}
        </span>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${statusTone(status)}`}
          title={status}
        >
          {friendlyStatusLabel(status)}
        </span>
      </div>
      <motion.button
        type="button"
        onClick={onViewDetails}
        className="shrink-0 self-start rounded-lg border border-white/[0.1] bg-white/[0.03] px-3.5 py-2 text-sm font-medium text-lab-text transition-colors hover:border-white/[0.22] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500/35 sm:self-center"
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.98 }}
        transition={{ type: "spring", stiffness: 480, damping: 28 }}
      >
        View mail details
      </motion.button>
    </motion.div>
  );
}
