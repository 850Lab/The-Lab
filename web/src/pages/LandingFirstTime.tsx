import { motion } from "framer-motion";
import { useCallback, useState } from "react";
import { LandingDemoLeadForm } from "@/components/LandingDemoLeadForm";
import { PublicDemoInteractiveSection } from "@/components/PublicDemoInteractiveSection";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import type { PublicDemoRunResult } from "@/lib/publicDemoTypes";
import { Link } from "react-router-dom";

const heroContainer = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.06 },
  },
};

const heroItem = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
  },
};

export function LandingFirstTime() {
  const { token, emailVerified } = useAuth();
  const { workflowId, loading: wfLoading } = useCustomerWorkflow();
  const [lastDemoRun, setLastDemoRun] = useState<PublicDemoRunResult | null>(null);

  const handleRunSuccess = useCallback((result: PublicDemoRunResult) => {
    setLastDemoRun(result);
    window.requestAnimationFrame(() => {
      document.getElementById("lead-form")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }, []);

  const showContinueStrip = Boolean(
    token && emailVerified && !wfLoading && !workflowId,
  );

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[32%] z-0 h-[min(85vw,560px)] w-[min(85vw,560px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.1] blur-[100px]"
        aria-hidden
      />

      <TopBarMinimal hideLiveDemoLink />

      <div className="h-14 shrink-0" aria-hidden />

      {showContinueStrip ? (
        <div className="border-b border-white/[0.06] bg-lab-surface/85 px-4 py-2.5 text-center backdrop-blur-md">
          <Link
            to="/get-report"
            className="text-sm font-medium text-lab-accent hover:text-sky-300"
          >
            Continue your program — get your report
          </Link>
        </div>
      ) : null}

      <main className="relative z-10 mx-auto max-w-5xl px-4 pb-24 pt-8 sm:px-6 sm:pt-10">
        <motion.div
          className="mx-auto max-w-2xl"
          variants={heroContainer}
          initial="hidden"
          animate="show"
        >
          <div className="rounded-2xl border border-white/[0.09] bg-lab-surface/50 px-6 py-8 text-center shadow-[0_24px_80px_-32px_rgba(0,0,0,0.55)] backdrop-blur-md sm:px-10 sm:py-10">
            <motion.span
              variants={heroItem}
              data-testid="home-hero-eyebrow"
              className="inline-flex items-center rounded-full border border-white/10 bg-white/[0.04] px-3.5 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-lab-muted"
            >
              Interactive preview
            </motion.span>
            <motion.h1
              variants={heroItem}
              className="mt-5 text-balance text-3xl font-semibold leading-[1.15] tracking-tight text-lab-text sm:text-[2.25rem] sm:leading-[1.12]"
            >
              See the program in action
            </motion.h1>
            <motion.p
              variants={heroItem}
              className="mx-auto mt-5 max-w-lg text-pretty text-base leading-relaxed text-lab-muted sm:text-lg"
            >
              Run a sample with the same engine members use — parsing, priorities, bureau letters, and a
              72-hour plan.
            </motion.p>
            <motion.div
              variants={heroItem}
              className="mt-5 flex flex-wrap items-center justify-center gap-2"
              aria-label="Sample scenario types"
            >
              {["Rough credit", "Law-backed items", "Thin file"].map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-lab-accent/20 bg-lab-accent/[0.08] px-3 py-1 text-xs font-medium text-lab-text/90"
                >
                  {label}
                </span>
              ))}
            </motion.div>
            <motion.p
              variants={heroItem}
              className="mx-auto mt-5 flex max-w-md flex-wrap items-center justify-center gap-x-1.5 gap-y-1 text-pretty text-sm leading-snug text-lab-muted"
            >
              <span
                className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400"
                aria-hidden
              >
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </span>
              <span>Sample PDFs only — your own file is never uploaded here.</span>
            </motion.p>
            <motion.div
              variants={heroItem}
              className="mx-auto mt-6 max-w-md border-t border-white/[0.07] pt-6"
            >
              <p className="text-pretty text-sm leading-relaxed text-lab-subtle sm:text-[15px]">
                When you&apos;re done, tell us your plans — workshop, class, your file, or a referral.
              </p>
            </motion.div>
          </div>
        </motion.div>

        <div className="mt-8 sm:mt-10">
          <PublicDemoInteractiveSection
            onRunSuccess={handleRunSuccess}
            embeddedOnHome
          />
        </div>

        {lastDemoRun ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="mt-12 rounded-2xl border border-white/[0.08] bg-lab-surface/70 px-6 py-8 text-center shadow-lg shadow-black/15 sm:px-10"
            data-testid="demo-post-run-cta"
          >
            <p className="text-xs font-semibold uppercase tracking-[0.15em] text-lab-subtle">
              Next step
            </p>
            <h2 className="mt-2 text-xl font-semibold text-lab-text sm:text-2xl">
              Tell us your plans
            </h2>
            <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-lab-muted">
              Workshops, classes, your own file, or a referral — drop your details below and we&apos;ll
              follow up.
            </p>
          </motion.div>
        ) : null}

        <div className={lastDemoRun ? "mt-8 sm:mt-10" : "mt-16 sm:mt-20"}>
          <LandingDemoLeadForm lastDemoRun={lastDemoRun} />
        </div>
      </main>
    </div>
  );
}
