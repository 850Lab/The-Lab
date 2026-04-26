import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FindingGroupCard } from "@/components/FindingGroupCard";
import type { FindingGroupCardProps } from "@/components/FindingGroupCard";
import { resolveAnalysisNarrative } from "@/lib/analysisFindingsNarrative";
import type { ReviewClaimJson } from "@/lib/intakeTypes";
import { stepNestedStaggerVariants as groupsContainer } from "@/lib/motionStep";
import { useAnimatedCount } from "@/hooks/useAnimatedCount";

type Props = {
  claims: ReviewClaimJson[];
  findingGroups: FindingGroupCardProps[];
  authoritativeStepId: string | undefined;
  findingsContinueHref: string;
};

const primaryReveal = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
  },
};

export function AnalysisResultsExperience({
  claims,
  findingGroups,
  authoritativeStepId,
  findingsContinueHref,
}: Props) {
  const navigate = useNavigate();
  const [findingsOpen, setFindingsOpen] = useState(false);
  const narrative = useMemo(() => resolveAnalysisNarrative(claims), [claims]);
  const total = claims.length;
  const countDisplay = useAnimatedCount(total, 720, total > 0);
  const highImpactDisplay = useAnimatedCount(
    narrative.showHighImpact ? narrative.matchingCount : 0,
    600,
    narrative.showHighImpact && total > 0,
  );

  return (
    <div className="rounded-2xl border border-neutral-200/90 bg-white px-5 py-8 shadow-[0_1px_0_0_rgba(255,255,255,0.9)_inset,0_24px_60px_-36px_rgba(15,23,42,0.12)] sm:px-8 sm:py-9">
      <p className="text-center text-[10px] font-semibold uppercase tracking-[0.22em] text-neutral-500">
        Step 2 of 3
      </p>

      <motion.h1
        className="mx-auto mt-3 max-w-xl text-balance text-center font-heading text-[1.5rem] font-semibold leading-[1.12] tracking-[-0.03em] text-neutral-950 sm:text-[1.85rem]"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        {narrative.headline}
      </motion.h1>

      <div className="mx-auto mt-5 flex max-w-md flex-wrap items-end justify-center gap-6 sm:gap-10">
        <div className="text-center">
          <p
            className="font-heading text-4xl font-bold tabular-nums text-neutral-950 sm:text-5xl"
            aria-live="polite"
          >
            {countDisplay}
          </p>
          <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-500">
            On your report
          </p>
        </div>
        {narrative.showHighImpact ? (
          <div className="text-center">
            <p
              className="font-heading text-4xl font-bold tabular-nums text-emerald-800 sm:text-5xl"
              aria-live="polite"
            >
              {highImpactDisplay}
            </p>
            <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-neutral-500">
              High-impact focus
            </p>
          </div>
        ) : null}
      </div>

      <p className="mx-auto mt-3 max-w-md text-center text-xs text-neutral-500">
        Private review — nothing is mailed from this step.{" "}
        <Link
          to="/report"
          className="font-medium text-neutral-800 underline decoration-neutral-300 underline-offset-2 hover:text-neutral-950"
        >
          Full breakdown in your report
        </Link>
        .
      </p>

      <motion.article
        className="relative mx-auto mt-7 max-w-lg overflow-hidden rounded-xl border border-neutral-300/80 bg-gradient-to-b from-neutral-50 to-white px-5 py-5 shadow-[0_0_0_1px_rgba(255,255,255,0.8)_inset,0_18px_40px_-28px_rgba(15,23,42,0.15)] sm:px-6 sm:py-6"
        variants={primaryReveal}
        initial="hidden"
        animate="show"
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-neutral-400/45 to-transparent" />
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold tracking-tight text-neutral-950 sm:text-xl">
            {narrative.primaryTitle}
          </h2>
          {narrative.showHighImpact ? (
            <span className="rounded-md border border-neutral-400/50 bg-neutral-100/90 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-600">
              High impact
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-sm font-medium leading-snug text-neutral-800">{narrative.primaryLines[0]}</p>
        <details className="details-calm group mt-3">
          <summary className="cursor-pointer list-none text-left text-xs font-medium text-neutral-500 marker:content-none [&::-webkit-details-marker]:hidden">
            <span className="underline decoration-neutral-200 underline-offset-2 group-open:text-neutral-800">
              More detail
            </span>
          </summary>
          <p className="mt-2 text-sm leading-relaxed text-neutral-600">{narrative.primaryLines[1]}</p>
        </details>
      </motion.article>

      {findingGroups.length > 0 ? (
        <div className="mt-8">
          <button
            type="button"
            onClick={() => setFindingsOpen((o) => !o)}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-neutral-300/70 bg-neutral-50/80 py-3 text-sm font-semibold text-neutral-800 transition-[background-color,border-color,transform] duration-200 hover:border-neutral-400 hover:bg-neutral-100/90 active:scale-[0.995]"
            aria-expanded={findingsOpen}
          >
            <span>{findingsOpen ? "Hide full findings" : "View all findings"}</span>
            <motion.span
              animate={{ rotate: findingsOpen ? 180 : 0 }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="text-neutral-500"
              aria-hidden
            >
              ▾
            </motion.span>
          </button>

          <AnimatePresence initial={false}>
            {findingsOpen ? (
              <motion.div
                key="all-findings"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden"
              >
                <p className="mb-4 mt-6 text-center text-[11px] font-semibold uppercase tracking-[0.14em] text-neutral-500">
                  By category
                </p>
                <motion.div
                  variants={groupsContainer}
                  initial="hidden"
                  animate="show"
                  className="space-y-5"
                >
                  {findingGroups.map((group) => (
                    <FindingGroupCard key={group.title} {...group} featured={false} surface="light" />
                  ))}
                </motion.div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      ) : null}

      <div className="mx-auto mt-10 max-w-md border-t border-neutral-200 pt-8 text-center">
        {authoritativeStepId === "review_claims" ? (
          <>
            <button
              type="button"
              onClick={() => navigate("/prepare")}
              className="w-full rounded-xl bg-neutral-950 py-3.5 text-[15px] font-semibold text-white shadow-[0_1px_0_0_rgba(255,255,255,0.08)_inset,0_8px_24px_-8px_rgba(0,0,0,0.35)] transition-[transform,box-shadow] duration-200 hover:shadow-[0_1px_0_0_rgba(255,255,255,0.1)_inset,0_10px_28px_-8px_rgba(0,0,0,0.4)] active:scale-[0.995]"
            >
              Let&apos;s fix this
            </button>
            <Link
              to="/upload"
              className="mt-3 inline-flex w-full items-center justify-center rounded-xl border border-neutral-300 bg-white py-3.5 text-[15px] font-semibold text-neutral-800 transition-colors hover:border-neutral-400 hover:bg-neutral-50"
            >
              Add another report
            </Link>
            <p className="mt-3 text-xs leading-relaxed text-neutral-500">
              Next you&apos;ll confirm your list — then strategy. Still your call.
            </p>
          </>
        ) : (
          <Link
            to={findingsContinueHref}
            className="inline-flex w-full items-center justify-center rounded-xl bg-neutral-950 py-3.5 text-[15px] font-semibold text-white shadow-[0_1px_0_0_rgba(255,255,255,0.08)_inset,0_8px_24px_-8px_rgba(0,0,0,0.35)] transition-[transform,box-shadow] duration-200 hover:shadow-[0_1px_0_0_rgba(255,255,255,0.1)_inset,0_10px_28px_-8px_rgba(0,0,0,0.4)] active:scale-[0.995]"
          >
            Continue in your program
          </Link>
        )}
      </div>
    </div>
  );
}
