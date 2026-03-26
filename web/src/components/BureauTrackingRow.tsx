import { motion } from "framer-motion";
import type { BureauMainStatus } from "@/lib/mockTrackingData";

type Props = {
  bureau: string;
  status: BureauMainStatus;
  onViewTracking: () => void;
};

function statusTone(s: BureauMainStatus): string {
  switch (s) {
    case "Delivered":
      return "text-emerald-300/95 bg-emerald-500/12";
    case "In transit":
      return "text-sky-200/95 bg-sky-500/12";
    case "Needs attention":
      return "text-amber-200/95 bg-amber-500/12";
    default:
      return "text-lab-muted bg-white/[0.06]";
  }
}

export function BureauTrackingRow({ bureau, status, onViewTracking }: Props) {
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
        >
          {status}
        </span>
      </div>
      <motion.button
        type="button"
        onClick={onViewTracking}
        className="shrink-0 self-start rounded-lg border border-white/[0.1] bg-white/[0.03] px-3.5 py-2 text-sm font-medium text-lab-text transition-colors hover:border-lab-accent/35 hover:bg-lab-accent/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35 sm:self-center"
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.98 }}
        transition={{ type: "spring", stiffness: 480, damping: 28 }}
      >
        View tracking
      </motion.button>
    </motion.div>
  );
}
