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
    if (!token || !emailVerified) {
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

  const canStart = Boolean(token && emailVerified);

  return (
    <div className="relative flex min-h-screen flex-col bg-lab-bg">
      <StartTransitionOverlay open={overlayOpen} />

      <div
        className="pointer-events-none absolute left-1/2 top-1/2 z-0 h-[min(85vw,640px)] w-[min(85vw,640px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.14] blur-[100px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 z-0 h-[min(55vw,420px)] w-[min(55vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.06] blur-[80px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto flex flex-1 max-w-2xl flex-col items-center justify-center px-4 pb-16 sm:px-6">
        <motion.div
          className="flex flex-col items-center text-center"
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

          <motion.div variants={heroItem} className="mt-12 w-full sm:mt-14">
            <ProcessStripAnimated />
          </motion.div>

          <motion.div
            variants={heroItem}
            className="mt-12 flex flex-col items-center gap-3 sm:mt-14"
          >
            <motion.button
              type="button"
              onClick={handleStart}
              disabled={overlayOpen || !canStart}
              title={
                !token
                  ? "Sign in to start."
                  : !emailVerified
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
