import { useCallback, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

/** Visitor-facing stages (3). Internal visuals stay realistic; labels stay plain. */
const STAGES = [
  {
    key: "found",
    pill: "What we found",
    headline: "We found inconsistencies",
    sub: "The same account can read differently in different places — we call that out clearly.",
  },
  {
    key: "shifted",
    pill: "What shifted",
    headline: "This changed the strategy",
    sub: "Once we know what's off, the next steps narrow to what actually applies to your situation.",
  },
  {
    key: "letter",
    pill: "Your letter",
    headline: "Here is the generated letter",
    sub: "A ready-to-use dispute letter you can review, download, and send.",
  },
] as const;

const PLAIN_ISSUES = [
  "Payment history doesn't match across your reports",
  "Account status reads differently depending on the bureau",
  "What you were told doesn't match what's listed",
] as const;

const BUREAU_CHIPS = ["Equifax", "Experian", "TransUnion"] as const;

/** Safe illustrative sample — real runs produce your letters inside the app. */
const SAMPLE_LETTER_BODY = `850 Lab — Dispute letter (sample)

January 1, 2026

Equifax Information Services LLC
P.O. Box 740256
Atlanta, GA 30374

Re: Dispute of inaccurate information

Dear Sir or Madam,

I am writing to dispute inaccurate information on my credit report. The following item(s) appear inconsistent with my records and require reinvestigation under applicable law.

Account / reference: SAMPLE-TRADELINE-001
Issue: Reported late payment status conflicts with payment history reflected on another bureau file for the same obligation.

Please investigate, correct any inaccuracies, and provide the results of your investigation.

Sincerely,

[Consumer name]
[Address]
[Phone]`;

function downloadSampleLetter() {
  const blob = new Blob([SAMPLE_LETTER_BODY], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "850-lab-sample-dispute-letter.txt";
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const panelMotion = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.22 } },
};

type Props = {
  onScrollToLiveDemo: () => void;
};

export function LandingGuidedDemoFlow({ onScrollToLiveDemo }: Props) {
  const [stage, setStage] = useState(0);
  const maxStage = STAGES.length - 1;

  const goNext = useCallback(() => {
    setStage((s) => Math.min(s + 1, maxStage));
  }, [maxStage]);

  const goPrev = useCallback(() => {
    setStage((s) => Math.max(s - 1, 0));
  }, []);

  const meta = useMemo(() => STAGES[stage], [stage]);

  return (
    <section
      id="watch-it-work"
      className="relative z-10 mx-auto mt-20 max-w-5xl scroll-mt-28 px-4 sm:mt-24 sm:px-6"
    >
      <div className="text-center">
        <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-neutral-400">
          Product walkthrough
        </p>
        <h2 className="mt-2 font-heading text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          See it in three steps
        </h2>
        <p className="mx-auto mt-3 max-w-lg text-sm font-medium leading-relaxed text-neutral-200">
          No sample PDFs required for this preview — it shows how the experience feels end to end.
        </p>
      </div>

      {/* Proof forward: sample letter always one click away */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-20px" }}
        className="relative mt-8 overflow-hidden rounded-xl border-2 border-white/20 bg-gradient-to-br from-white/[0.08] via-white/[0.04] to-transparent px-4 py-4 shadow-[0_0_48px_-16px_rgba(255,255,255,0.06)] sm:px-6 sm:py-5"
      >
        <div className="flex flex-col items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
          <div className="text-left">
            <p className="text-xs font-bold uppercase tracking-wider text-zinc-300/90">Proof</p>
            <p className="mt-1 text-sm font-semibold text-white sm:text-base">
              Real systems produce real letters — download a sample to see the format.
            </p>
          </div>
          <motion.button
            type="button"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={downloadSampleLetter}
            className="shrink-0 rounded-lg bg-white px-6 py-3.5 text-sm font-bold text-lab-bg shadow-lg shadow-black/25 ring-2 ring-white/40 hover:bg-neutral-100"
          >
            Download sample letter
          </motion.button>
        </div>
      </motion.div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
        {STAGES.map((s, i) => (
          <button
            key={s.key}
            type="button"
            onClick={() => setStage(i)}
            className={`rounded-full px-4 py-2 text-xs font-bold transition-colors ${
              i === stage
                ? "bg-white text-lab-bg ring-2 ring-zinc-400/50"
                : i < stage
                  ? "border-2 border-white/25 bg-white/15 text-white hover:bg-white/20"
                  : "border border-white/15 text-neutral-400 hover:border-white/25 hover:text-neutral-200"
            }`}
          >
            {i + 1}. {s.pill}
          </button>
        ))}
      </div>

      <div className="relative mt-6 min-h-[340px] overflow-hidden rounded-2xl border-2 border-white/20 bg-white/[0.08] p-5 shadow-[0_32px_64px_-32px_rgba(0,0,0,0.75)] backdrop-blur-md sm:min-h-[380px] sm:p-8">
        <div className="mb-5 flex flex-col gap-4 border-b border-white/15 pb-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-neutral-400">
              Step {stage + 1} of {STAGES.length}
            </p>
            <h3 className="mt-1 font-heading text-lg font-semibold text-white sm:text-xl">{meta.headline}</h3>
            <p className="mt-1 max-w-xl text-sm text-neutral-200">{meta.sub}</p>
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={goPrev}
              disabled={stage === 0}
              className="rounded-lg border-2 border-white/20 bg-white/5 px-4 py-2 text-xs font-bold text-neutral-200 transition-colors hover:bg-white/10 disabled:opacity-35"
            >
              Back
            </button>
            <button
              type="button"
              onClick={goNext}
              disabled={stage === maxStage}
              className="rounded-lg bg-lab-accent px-4 py-2 text-xs font-bold text-white shadow-lg shadow-black/35 hover:brightness-110 disabled:opacity-35"
            >
              Next
            </button>
          </div>
        </div>

        <AnimatePresence mode="wait">
          {stage === 0 ? (
            <motion.div key="found" {...panelMotion} className="space-y-3">
              <p className="text-xs font-semibold text-neutral-300">Your report at a glance</p>
              <div className="rounded-xl border border-white/15 bg-lab-bg/50 p-4">
                <div className="grid gap-2">
                  {PLAIN_ISSUES.map((line, i) => (
                    <motion.div
                      key={line}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: 0.08 * i }}
                      className="flex items-center justify-between gap-3 rounded-lg border border-amber-400/35 bg-amber-500/10 px-3 py-3"
                    >
                      <span className="text-left text-sm font-medium text-white">{line}</span>
                      <span className="shrink-0 rounded-md bg-white/15 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-amber-100">
                        Look closer
                      </span>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          ) : null}

          {stage === 1 ? (
            <motion.div key="shift" {...panelMotion} className="space-y-4">
              <p className="text-xs font-semibold text-neutral-300">How the approach shifts</p>
              <div className="flex flex-col items-stretch gap-4 md:flex-row md:items-stretch">
                <div className="flex-1 rounded-xl border border-white/15 bg-lab-bg/40 p-4 opacity-80">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-neutral-500">Before</p>
                  <p className="mt-2 text-sm font-medium text-neutral-300">Broad, generic next steps</p>
                </div>
                <div className="flex h-12 w-12 shrink-0 items-center justify-center self-center rounded-full border-2 border-white/25 bg-white/[0.08] text-lg font-bold text-zinc-300">
                  →
                </div>
                <motion.div
                  className="flex-1 rounded-xl border-2 border-white/25 bg-white/[0.06] p-4 shadow-[0_0_40px_-12px_rgba(255,255,255,0.06)]"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                >
                  <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-300">After</p>
                  <p className="mt-2 text-sm font-semibold text-white">
                    Focused steps based on what we actually found on your file
                  </p>
                </motion.div>
              </div>
            </motion.div>
          ) : null}

          {stage === 2 ? (
            <motion.div key="letter" {...panelMotion} className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                {BUREAU_CHIPS.map((b) => (
                  <span
                    key={b}
                    className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold text-white"
                  >
                    {b}
                  </span>
                ))}
              </div>
              <div className="rounded-xl border-2 border-white/25 bg-[#0a0a0a] p-1 shadow-inner shadow-black/40">
                <div className="max-h-[min(52vh,320px)] overflow-y-auto rounded-lg border border-white/10 bg-white/[0.03] p-4 sm:p-5">
                  <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-neutral-200 sm:text-xs">
                    {SAMPLE_LETTER_BODY}
                  </pre>
                </div>
              </div>
              <motion.button
                type="button"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={downloadSampleLetter}
                className="w-full rounded-xl bg-white py-4 text-center text-base font-bold text-lab-bg shadow-[0_12px_40px_-12px_rgba(255,255,255,0.35)] ring-2 ring-white/30 hover:bg-neutral-100 sm:w-auto sm:px-10"
              >
                Download this sample letter
              </motion.button>
              <p className="text-center text-xs font-medium text-neutral-400 sm:text-left">
                When you run the live demo below, letters are generated from real fixture files — not
                mock filler.
              </p>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      <motion.div
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center"
      >
        <button
          type="button"
          onClick={onScrollToLiveDemo}
          className="rounded-xl border-2 border-white/25 bg-white/10 px-7 py-3.5 text-sm font-bold text-white transition-colors hover:border-white/40 hover:bg-white/15"
        >
          Try it on real sample files
        </button>
        <span className="max-w-sm text-center text-xs font-medium text-neutral-400 sm:text-left">
          Same flow with live data from PDFs — pick a scenario and watch it run.
        </span>
      </motion.div>
    </section>
  );
}
