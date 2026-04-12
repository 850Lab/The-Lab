import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { FindingGroupCard } from "@/components/FindingGroupCard";
import type { FindingGroupCardProps } from "@/components/FindingGroupCard";
import { resolveAnalysisNarrative } from "@/lib/analysisFindingsNarrative";
import type { ReviewClaimJson } from "@/lib/intakeTypes";
import { stepNestedStaggerVariants as groupsContainer } from "@/lib/motionStep";

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

  return (
    <div className="rounded-2xl border border-neutral-200/90 bg-white px-5 py-9 shadow-[0_1px_0_0_rgba(255,255,255,0.9)_inset,0_24px_60px_-36px_rgba(15,23,42,0.12)] sm:px-8 sm:py-11">
      <p className="text-center text-[10px] font-semibold uppercase tracking-[0.22em] text-neutral-500">
        Step 2 of 3
      </p>

      <motion.h1
        className="mx-auto mt-3 max-w-xl text-balance text-center font-heading text-[1.65rem] font-semibold leading-[1.12] tracking-[-0.03em] text-neutral-950 sm:text-[2rem]"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      >
        {narrative.headline}
      </motion.h1>

      <motion.p
        className="mx-auto mt-3 max-w-md text-center text-sm font-medium text-neutral-600"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.06, duration: 0.4 }}
      >
        {total} {total === 1 ? "item" : "items"} identified affecting your credit
      </motion.p>

      <p className="mx-auto mt-2 max-w-lg text-center text-xs leading-relaxed text-neutral-500">
        Private review only — nothing is mailed to the bureaus from this step.
      </p>

      <motion.article
        className="relative mx-auto mt-8 max-w-lg overflow-hidden rounded-xl border border-neutral-300/80 bg-gradient-to-b from-neutral-50 to-white px-5 py-6 shadow-[0_0_0_1px_rgba(255,255,255,0.8)_inset,0_18px_40px_-28px_rgba(15,23,42,0.15)] sm:px-6 sm:py-7"
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
        <p className="mt-3 text-sm leading-relaxed text-neutral-700">{narrative.primaryLines[0]}</p>
        <p className="mt-2 text-sm leading-relaxed text-neutral-600">{narrative.primaryLines[1]}</p>
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
