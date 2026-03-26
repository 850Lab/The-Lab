import { AnimatePresence, motion } from "framer-motion";
import { DisputeItemRow } from "@/components/DisputeItemRow";

export type DisputeGroupItem = {
  id: string;
  company: string;
  issueLabel: string;
  /** Stable order for stagger timing (unchanged when siblings are removed) */
  order: number;
};

type Props = {
  title: string;
  items: DisputeGroupItem[];
  onRemoveItem: (id: string) => void;
  groupVariants?: {
    hidden: { opacity: number; y: number };
    show: {
      opacity: number;
      y: number;
      transition: { duration: number; ease: number[] };
    };
  };
};

const rowVariants = {
  hidden: { opacity: 0, y: 8 },
  show: (order: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: Math.min(order, 14) * 0.042,
      duration: 0.3,
      ease: [0.22, 1, 0.36, 1],
    },
  }),
  exit: {
    opacity: 0,
    y: -8,
    transition: { duration: 0.26, ease: [0.22, 1, 0.36, 1] },
  },
};

const defaultGroupVariants = {
  hidden: { opacity: 0, y: 20 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
  },
};

export function DisputeGroupCard({
  title,
  items,
  onRemoveItem,
  groupVariants = defaultGroupVariants,
}: Props) {
  const count = items.length;

  return (
    <motion.section
      layout
      variants={groupVariants}
      className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 shadow-sm shadow-black/20 sm:px-6 sm:py-6"
    >
      <div className="border-b border-white/[0.06] pb-4">
        <h2 className="text-lg font-semibold text-lab-text">
          {title} ({count})
        </h2>
        <p className="mt-1.5 text-sm text-lab-muted">We’ll challenge these for you</p>
      </div>

      <div className="divide-y divide-white/[0.06] pt-1">
        <AnimatePresence initial={false} mode="popLayout">
          {items.map((item) => (
            <motion.div
              key={item.id}
              layout
              custom={item.order}
              variants={rowVariants}
              initial="hidden"
              animate="show"
              exit="exit"
              transition={{ layout: { duration: 0.34, ease: [0.22, 1, 0.36, 1] } }}
            >
              <DisputeItemRow
                company={item.company}
                issueLabel={item.issueLabel}
                onRemove={() => onRemoveItem(item.id)}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {count === 0 ? (
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="py-6 text-center text-sm text-lab-subtle"
        >
          No items in this group
        </motion.p>
      ) : null}
    </motion.section>
  );
}
