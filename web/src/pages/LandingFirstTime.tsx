import { motion } from "framer-motion";
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { LandingDemoLeadForm } from "@/components/LandingDemoLeadForm";
import { PublicDemoInteractiveSection } from "@/components/PublicDemoInteractiveSection";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { LandingAmbientLayer } from "@/components/landing/LandingAmbientLayer";
import { LandingAuthorityStrip } from "@/components/landing/LandingAuthorityStrip";
import { LandingEarlyAccessModal } from "@/components/landing/LandingEarlyAccessModal";
import { LandingFlowStrip } from "@/components/landing/LandingFlowStrip";
import { LandingGuidedDemoFlow } from "@/components/landing/LandingGuidedDemoFlow";
import { LandingPremiumHero } from "@/components/landing/LandingPremiumHero";
import { buildProgramSignupHref, writeDemoProgramBridge } from "@/lib/demoProgramBridge";
import type { PublicDemoRunResult } from "@/lib/publicDemoTypes";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

export function LandingFirstTime() {
  const { token, emailVerified } = useAuth();
  const { workflowId, loading: wfLoading } = useCustomerWorkflow();
  const [lastDemoRun, setLastDemoRun] = useState<PublicDemoRunResult | null>(null);
  const [accessOpen, setAccessOpen] = useState(false);

  const scrollWatch = useCallback(() => {
    document.getElementById("watch-it-work")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, []);

  const scrollLive = useCallback(() => {
    document.getElementById("live-demo")?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, []);

  const handleRunSuccess = useCallback((result: PublicDemoRunResult) => {
    setLastDemoRun(result);
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById("demo-post-run-cta")?.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      });
    });
  }, []);

  const showContinueStrip = Boolean(
    token && emailVerified && !wfLoading && !workflowId,
  );

  return (
    <div className="relative min-h-full bg-lab-bg text-lab-text">
      <LandingAmbientLayer />
      <TopBarMinimal hideLiveDemoLink />

      <div className="h-14 shrink-0" aria-hidden />

      {showContinueStrip ? (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative z-10 border-b border-white/15 bg-white/[0.08] px-4 py-2.5 text-center backdrop-blur-md"
        >
          <Link
            to="/get-report"
            className="text-sm font-semibold text-lab-accent underline decoration-white/15 underline-offset-4 transition-colors hover:decoration-zinc-400/50"
          >
            Pick up where you left off — grab your report, then upload
          </Link>
        </motion.div>
      ) : null}

      <main className="relative z-10 mx-auto max-w-5xl px-4 pb-28 pt-8 sm:px-6 sm:pt-12">
        <LandingPremiumHero
          startReportTo={buildProgramSignupHref({ next: "/upload" })}
          onSeeDemo={scrollWatch}
          onEarlyAccess={() => setAccessOpen(true)}
        />
        <LandingFlowStrip />
        <LandingGuidedDemoFlow onScrollToLiveDemo={scrollLive} />
        <LandingAuthorityStrip />

        <div className="mx-auto mt-4 max-w-5xl text-center sm:mt-8">
          <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-neutral-400">
            See it work
          </p>
          <h3 className="mt-2 font-heading text-xl font-semibold tracking-tight text-white sm:text-2xl">
            Upload → findings → letters → what to do next
          </h3>
          <p className="mx-auto mt-2 max-w-lg text-sm font-medium text-neutral-200">
            Sample PDFs only here — your file stays private until you start your own report.
          </p>
        </div>

        <div className="mt-8 sm:mt-10">
          <PublicDemoInteractiveSection
            onRunSuccess={handleRunSuccess}
            embeddedOnHome
            surfaceTheme="night"
          />
        </div>

        <div
          id="start-report"
          className="mx-auto mt-10 max-w-md scroll-mt-28 text-center sm:mt-12"
        >
          <Link
            to={buildProgramSignupHref({ next: "/upload" })}
            onClick={() => writeDemoProgramBridge({ source: "demo_welcome" })}
            className="inline-flex w-full items-center justify-center rounded-2xl bg-white px-6 py-3.5 text-[15px] font-semibold text-lab-bg shadow-[0_12px_40px_-16px_rgba(255,255,255,0.35)] ring-1 ring-white/30 transition-shadow hover:shadow-[0_16px_48px_-12px_rgba(255,255,255,0.4)] sm:w-auto sm:min-w-[240px]"
          >
            Start my report
          </Link>
          <p className="mt-2.5 text-xs font-medium text-neutral-400">Free to begin · account required to save</p>
        </div>

        {lastDemoRun ? (
          <motion.div
            id="demo-post-run-cta"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="mt-10 rounded-2xl border border-white/15 bg-white/[0.06] px-6 py-6 text-center shadow-lg shadow-black/20 backdrop-blur-sm sm:px-8"
            data-testid="demo-post-run-cta"
          >
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">What&apos;s next</p>
            <h2 className="mt-2 font-heading text-lg font-semibold text-white sm:text-xl">
              That same path works on your real report
            </h2>
            <div className="mt-4 flex flex-col items-center justify-center gap-2 sm:flex-row sm:gap-3">
              <Link
                to={buildProgramSignupHref({ next: "/upload" })}
                onClick={() => writeDemoProgramBridge({ source: "demo_run", workflowId: lastDemoRun.workflowId })}
                className="inline-flex w-full items-center justify-center rounded-xl bg-white px-5 py-3 text-sm font-semibold text-lab-bg shadow-md shadow-black/20 sm:w-auto"
              >
                Start my report
              </Link>
            </div>
            <p className="mx-auto mt-3 max-w-md text-xs leading-relaxed text-neutral-300">
              Or use the form below if you want us to follow up.
            </p>
          </motion.div>
        ) : null}

        <div className={lastDemoRun ? "mt-8 sm:mt-10" : "mt-16 sm:mt-20"}>
          <LandingDemoLeadForm lastDemoRun={lastDemoRun} variant="dark" />
        </div>
      </main>

      <LandingEarlyAccessModal
        open={accessOpen}
        onClose={() => setAccessOpen(false)}
        mode="open"
      />
    </div>
  );
}
