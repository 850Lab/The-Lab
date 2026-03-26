import { motion } from "framer-motion";

type Props = {
  bureau: string;
  statusLabel?: string;
};

export function BureauSendStatusRow({
  bureau,
  statusLabel = "Sent",
}: Props) {
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
      className="flex items-center justify-between gap-4 rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-3.5 sm:px-5 sm:py-4"
    >
      <div className="flex min-w-0 items-center gap-3">
        <span
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-500/12 text-emerald-400"
          aria-hidden
        >
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
              d="M5 13l4 4L19 7"
            />
          </svg>
        </span>
        <span className="truncate text-[15px] font-medium text-lab-text sm:text-base">
          {bureau}
        </span>
      </div>
      <span className="shrink-0 text-sm font-medium text-emerald-300/90">
        {statusLabel}
      </span>
    </motion.div>
  );
}
