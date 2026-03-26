import { AnimatePresence, motion } from "framer-motion";

type Props = {
  open: boolean;
};

export function StartTransitionOverlay({ open }: Props) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="start-overlay"
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-lab-bg/[0.94] px-6 backdrop-blur-md"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
        >
          <motion.div
            className="h-1 w-10 overflow-hidden rounded-full bg-lab-elevated"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.08 }}
          >
            <motion.div
              className="h-full w-1/2 rounded-full bg-lab-accent/80"
              animate={{ x: ["-100%", "280%"] }}
              transition={{
                duration: 1.1,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          </motion.div>
          <motion.p
            className="text-center text-base font-medium text-lab-text sm:text-lg"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            Starting your analysis…
          </motion.p>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
