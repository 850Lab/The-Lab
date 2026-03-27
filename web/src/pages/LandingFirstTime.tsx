import { motion } from "framer-motion";
import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ProcessStripAnimated } from "@/components/ProcessStripAnimated";
import { StartTransitionOverlay } from "@/components/StartTransitionOverlay";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const heroContainer = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.14,
    },
  },
};

const heroItem = {
  hidden: { opacity: 0, y: 18 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  },
};

export function LandingFirstTime() {
  const navigate = useNavigate();
  const [overlayOpen, setOverlayOpen] = useState(false);
  const { token, emailVerified } = useAuth();
  const { initWorkflow } = useCustomerWorkflow();

  const handleStart = useCallback(() => {
    if (token && !emailVerified) {
      return;
    }
    if (!token) {
      navigate("/get-report", { replace: true });
      return;
    }
    setOverlayOpen(true);
    void (async () => {
      try {
        await initWorkflow();
        window.setTimeout(() => {
          navigate("/get-report", { replace: true });
          setOverlayOpen(false);
        }, 1250);
      } catch {
        setOverlayOpen(false);
      }
    })();
  }, [navigate, initWorkflow, token, emailVerified]);

  /** Guests can start immediately; signed-in users must verify email before continuing. */
  const startDisabled = Boolean(token && !emailVerified);

  return (
    <div className="relative min-h-full bg-lab-bg">
      <StartTransitionOverlay open={overlayOpen} />

      <div
        className="pointer-events-none absolute left-1/2 top-[38%] z-0 h-[min(85vw,640px)] w-[min(85vw,640px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.14] blur-[100px] sm:top-[40%]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[42%] z-0 h-[min(55vw,420px)] w-[min(55vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.06] blur-[80px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto flex min-h-full max-w-2xl flex-col px-4 pb-16 pt-24 sm:px-6 sm:pt-28">
        <motion.div
          className="flex flex-1 flex-col items-center justify-center text-center"
          variants={heroContainer}
          initial="hidden"
          animate="show"
        >
          <motion.h1
            variants={heroItem}
            className="max-w-[20ch] text-balance text-3xl font-semibold leading-tight tracking-tight text-lab-text sm:max-w-none sm:text-4xl sm:leading-tight md:text-[2.5rem]"
          >
            Turn your credit report into real action
          </motion.h1>

          <motion.p
            variants={heroItem}
            className="mt-5 max-w-md text-pretty text-base leading-relaxed text-lab-muted sm:text-lg"
          >
            Upload your report, review what we found, and we’ll help you move
            forward step by step.
          </motion.p>

          <motion.div
            variants={heroItem}
            className="mx-auto mt-12 w-full max-w-md sm:mt-14 sm:max-w-lg"
          >
            <ProcessStripAnimated />
          </motion.div>

          <motion.div
            variants={heroItem}
            className="mt-12 flex flex-col items-center gap-3 sm:mt-14"
          >
            <motion.button
              type="button"
              onClick={handleStart}
              disabled={overlayOpen || startDisabled}
              title={
                token && !emailVerified
                  ? "Verify your email to continue."
                  : undefined
              }
              className="rounded-lg bg-lab-accent px-8 py-3 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/20 outline-none ring-lab-accent/40 transition-shadow focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-60"
              whileHover={{
                scale: 1.02,
                boxShadow: "0 12px 40px -8px rgba(59,130,246,0.45)",
              }}
              whileTap={{ scale: 0.98 }}
              transition={{ type: "spring", stiffness: 420, damping: 24 }}
            >
              Start now
            </motion.button>
            {!token ? (
              <>
                <p className="max-w-sm text-center text-xs leading-relaxed text-lab-subtle">
                  No account needed to explore. Create a free account when you&apos;re ready to
                  upload your report and save your progress.
                </p>
                <div className="flex flex-wrap items-center justify-center gap-4 text-sm">
                  <Link
                    to="/login"
                    className="font-medium text-lab-accent hover:text-sky-300"
                  >
                    Sign in
                  </Link>
                  <span className="text-lab-subtle">·</span>
                  <Link
                    to="/signup"
                    className="font-medium text-lab-accent hover:text-sky-300"
                  >
                    Create account
                  </Link>
                </div>
              </>
            ) : null}
          </motion.div>

          <motion.p
            variants={heroItem}
            className="mt-6 text-sm text-lab-subtle sm:mt-8"
          >
            No guesswork. Just a guided path forward.
          </motion.p>
        </motion.div>
      </main>
    </div>
  );
}
