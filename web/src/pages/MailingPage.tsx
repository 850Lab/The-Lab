import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MailingCTASection } from "@/components/MailingCTASection";
import { SendingState } from "@/components/SendingState";
import { SentState } from "@/components/SentState";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { setWorkflowStep } from "@/lib/workflow";

const SENDING_MS = 2400;

const headerVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

export function MailingPage() {
  const navigate = useNavigate();
  const [sent, setSent] = useState(false);

  useEffect(() => {
    const t = window.setTimeout(() => setSent(true), SENDING_MS);
    return () => window.clearTimeout(t);
  }, []);

  const handleTrack = () => {
    setWorkflowStep("tracking");
    navigate("/tracking", { replace: true });
  };

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[36%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[40%] z-0 h-[min(48vw,320px)] w-[min(48vw,320px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.04] blur-[90px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        <AnimatePresence mode="wait">
          {!sent ? (
            <motion.div
              key="sending"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            >
              <motion.p
                variants={headerVariants}
                initial="hidden"
                animate="show"
                className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
              >
                Sending
              </motion.p>
              <motion.h1
                variants={headerVariants}
                initial="hidden"
                animate="show"
                className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
              >
                We’re sending your disputes
              </motion.h1>
              <motion.p
                variants={headerVariants}
                initial="hidden"
                animate="show"
                className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
              >
                We’re submitting your letters and preparing tracking for each
                bureau.
              </motion.p>
              <SendingState />
            </motion.div>
          ) : (
            <motion.div
              key="sent"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.48, ease: [0.22, 1, 0.36, 1] }}
            >
              <motion.p
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.38, delay: 0.02 }}
                className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
              >
                Sent
              </motion.p>
              <SentState />
              <motion.div
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  delay: 0.55,
                  duration: 0.42,
                  ease: [0.22, 1, 0.36, 1],
                }}
              >
                <MailingCTASection onTrack={handleTrack} />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
