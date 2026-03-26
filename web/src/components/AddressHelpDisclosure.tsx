import { AnimatePresence, motion } from "framer-motion";
import { useId, useState } from "react";

export function AddressHelpDisclosure() {
  const [open, setOpen] = useState(false);
  const panelId = useId();

  return (
    <div className="mt-4 border-t border-white/[0.06] pt-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 rounded-lg py-1 text-left text-sm font-medium text-lab-accent transition-colors hover:text-sky-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/35"
      >
        <span>Don’t have one of these?</span>
        <motion.span
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          className="text-lab-muted"
          aria-hidden
        >
          ▼
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            id={panelId}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            <p className="pt-3 text-sm leading-relaxed text-lab-muted">
              That’s okay. Many people use a bank statement, insurance mailing,
              or official letter with your name and address. A lease, renter’s
              insurance, or voter registration notice often works too. Use the
              clearest document you have—we’ll review everything before
              anything is sent.
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
