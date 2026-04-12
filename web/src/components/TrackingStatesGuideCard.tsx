import { motion } from "framer-motion";
import { trackingQuietProgressMessage, trackingStatusGuideRows } from "@/lib/intelligenceExpression";

type Props = {
  /** When embedded (e.g. inside details), drop outer chrome. */
  embedded?: boolean;
};

export function TrackingStatesGuideCard({ embedded }: Props) {
  const rows = trackingStatusGuideRows();
  return (
    <motion.section
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className={
        embedded
          ? "px-0 py-0"
          : "rounded-xl border border-white/[0.08] bg-lab-surface/90 px-4 py-4 sm:px-5 sm:py-5"
      }
    >
      <h3 className="text-sm font-semibold text-lab-text">What the status labels mean</h3>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">{trackingQuietProgressMessage()}</p>
      <dl className="mt-4 space-y-3 border-t border-white/[0.06] pt-4">
        {rows.map((r) => (
          <div key={r.status}>
            <dt className="text-xs font-semibold text-lab-accent/95">{r.status}</dt>
            <dd className="mt-1 text-sm leading-relaxed text-lab-muted">{r.meaning}</dd>
          </div>
        ))}
      </dl>
    </motion.section>
  );
}
