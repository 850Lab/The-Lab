import { motion } from "framer-motion";
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { PublicDemoInteractiveSection } from "@/components/PublicDemoInteractiveSection";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { WaitlistLeadForm } from "@/components/WaitlistLeadForm";
import { LandingAmbientLayer } from "@/components/landing/LandingAmbientLayer";
import { LandingAuthorityStrip } from "@/components/landing/LandingAuthorityStrip";
import { LandingEarlyAccessModal } from "@/components/landing/LandingEarlyAccessModal";
import { LandingFourPillars } from "@/components/landing/LandingFourPillars";
import { LandingGuidedDemoFlow } from "@/components/landing/LandingGuidedDemoFlow";
import { LandingPremiumHero } from "@/components/landing/LandingPremiumHero";
import type { PublicDemoRunResult } from "@/lib/publicDemoTypes";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

export function LandingWaitlist() {
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
    <div className="relative min-h-full bg-lab-bg text-lab-text" data-testid="waitlist-page">
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
          waitlistHint
          onTryDemo={scrollWatch}
          onRunReport={() => setAccessOpen(true)}
        />
        <LandingFourPillars />
        <LandingGuidedDemoFlow onScrollToLiveDemo={scrollLive} />
        <LandingAuthorityStrip />

        <div className="mx-auto mt-4 max-w-5xl text-center sm:mt-8">
          <p
            data-testid="waitlist-demo-eyebrow"
            className="text-[10px] font-bold uppercase tracking-[0.28em] text-neutral-400"
          >
            Interactive demo
          </p>
          <h3 className="mt-2 font-heading text-xl font-semibold tracking-tight text-white sm:text-2xl">
            Real sample files · not your credit file
          </h3>
          <p className="mx-auto mt-2 max-w-lg text-sm font-medium text-neutral-200">
            We use shared PDFs here so you can see how it works before you&apos;re in.
          </p>
        </div>

        <div className="mt-8 sm:mt-10">
          <PublicDemoInteractiveSection
            onRunSuccess={handleRunSuccess}
            embeddedOnHome
            surfaceTheme="night"
          />
        </div>

        {lastDemoRun ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="mt-12 rounded-2xl border-2 border-white/20 bg-white/[0.08] px-6 py-8 text-center shadow-xl shadow-black/25 backdrop-blur-sm sm:px-10"
            data-testid="demo-post-run-cta"
          >
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">Next</p>
            <h2 className="mt-2 font-heading text-xl font-semibold text-white sm:text-2xl">
              Want yours to look like that?
            </h2>
            <p className="mx-auto mt-3 max-w-md text-sm font-medium leading-relaxed text-neutral-200">
              Get in line — we&apos;ll open the door when your turn comes.
            </p>
          </motion.div>
        ) : null}

        <div className={lastDemoRun ? "mt-8 sm:mt-10" : "mt-16 sm:mt-20"}>
          <WaitlistLeadForm variant="dark" />
        </div>
      </main>

      <LandingEarlyAccessModal
        open={accessOpen}
        onClose={() => setAccessOpen(false)}
        mode="waitlist"
      />
    </div>
  );
}
