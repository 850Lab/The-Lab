import { motion } from "framer-motion";
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { PublicDemoInteractiveSection } from "@/components/PublicDemoInteractiveSection";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { WaitlistLeadForm } from "@/components/WaitlistLeadForm";
import type { PublicDemoRunResult } from "@/lib/publicDemoTypes";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const heroContainer = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.09, delayChildren: 0.04 },
  },
};

const heroItem = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  },
};

export function LandingWaitlist() {
  const { token, emailVerified } = useAuth();
  const { workflowId, loading: wfLoading } = useCustomerWorkflow();
  const [lastDemoRun, setLastDemoRun] = useState<PublicDemoRunResult | null>(null);

  const handleRunSuccess = useCallback((result: PublicDemoRunResult) => {
    setLastDemoRun(result);
    window.requestAnimationFrame(() => {
      document.getElementById("waitlist")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }, []);

  const showContinueStrip = Boolean(
    token && emailVerified && !wfLoading && !workflowId,
  );

  return (
    <div className="relative min-h-full bg-white" data-testid="waitlist-page">
      <div
        className="pointer-events-none absolute left-1/2 top-[18%] z-0 h-[min(90vw,520px)] w-[min(90vw,520px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-br from-neutral-200/35 via-neutral-100/25 to-transparent blur-[100px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute right-[8%] top-[42%] z-0 h-[min(40vw,280px)] w-[min(40vw,280px)] rounded-full bg-gradient-to-tr from-neutral-300/20 to-transparent blur-[80px]"
        aria-hidden
      />

      <TopBarMinimal variant="light" />

      <div className="h-14 shrink-0" aria-hidden />

      {showContinueStrip ? (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="border-b border-neutral-200/80 bg-neutral-50/90 px-4 py-2.5 text-center backdrop-blur-sm"
        >
          <Link
            to="/get-report"
            className="text-sm font-semibold text-neutral-900 underline decoration-neutral-300/90 underline-offset-4 transition-colors hover:decoration-neutral-500"
          >
            Continue — get your report, then upload
          </Link>
        </motion.div>
      ) : null}

      <main className="relative z-10 mx-auto max-w-5xl px-4 pb-24 pt-6 sm:px-6 sm:pt-8">
        <motion.div
          className="mx-auto max-w-2xl"
          variants={heroContainer}
          initial="hidden"
          animate="show"
        >
          <div className="relative overflow-hidden rounded-2xl border border-neutral-200/90 bg-white px-6 py-9 text-center shadow-[0_24px_80px_-32px_rgba(15,23,42,0.14)] sm:px-10 sm:py-11">
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neutral-400/50 to-transparent"
              aria-hidden
            />
            <motion.span
              variants={heroItem}
              data-testid="home-hero-eyebrow"
              className="inline-flex items-center rounded-full border border-neutral-200/90 bg-neutral-50 px-3.5 py-1 text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-500"
            >
              Private early access
            </motion.span>
            <motion.h1
              variants={heroItem}
              data-testid="home-hero-headline"
              className="mt-5 text-balance text-3xl font-bold leading-[1.12] tracking-tight text-neutral-950 sm:text-[2.35rem] sm:leading-[1.08]"
            >
              Be first when 850 Lab opens
            </motion.h1>
            <motion.p
              variants={heroItem}
              className="mx-auto mt-4 max-w-lg text-pretty text-base font-medium leading-relaxed text-neutral-600 sm:text-lg"
            >
              The same bureau-grade engine members will use — invitation only while we finish the
              full guided experience. Join the waitlist for priority access.
            </motion.p>
            <motion.p
              variants={heroItem}
              className="mx-auto mt-6 max-w-md text-pretty text-sm font-medium leading-relaxed text-neutral-500"
            >
              Selective onboarding. Calm, precise, built for people who take credit seriously — not
              a mass-market signup wall.
            </motion.p>
          </div>
        </motion.div>

        <div className="mt-10 sm:mt-12">
          <PublicDemoInteractiveSection
            onRunSuccess={handleRunSuccess}
            embeddedOnHome
            surfaceTheme="day"
          />
        </div>

        {lastDemoRun ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="mt-12 rounded-2xl border border-neutral-200/90 bg-neutral-50/50 px-6 py-8 text-center shadow-sm shadow-neutral-900/5 sm:px-10"
            data-testid="demo-post-run-cta"
          >
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-neutral-500">
              Next
            </p>
            <h2 className="mt-2 text-xl font-bold text-neutral-950 sm:text-2xl">
              Request priority access
            </h2>
            <p className="mx-auto mt-3 max-w-md text-sm font-medium leading-relaxed text-neutral-600">
              The full program opens by invitation — join the waitlist below when you&apos;re ready.
            </p>
          </motion.div>
        ) : null}

        <div className={lastDemoRun ? "mt-8 sm:mt-10" : "mt-12 sm:mt-16"}>
          <WaitlistLeadForm />
        </div>
      </main>
    </div>
  );
}
