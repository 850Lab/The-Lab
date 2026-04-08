import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { CreditCommandPlanSection } from "@/components/CreditCommandPlanSection";
import { LetterPreviewModal } from "@/components/LetterPreviewModal";
import { PublicDemoBureauLetterStrip } from "@/components/PublicDemoBureauLetterStrip";
import {
  buildProgramSignupHref,
  writeDemoProgramBridge,
} from "@/lib/demoProgramBridge";
import { workflowApiBase } from "@/lib/apiBase";
import {
  classifyPublicDemoScenariosError,
  fetchPublicDemoScenarios,
  runPublicDemoScenario,
  type PublicDemoUnavailableCopy,
} from "@/lib/publicDemoApi";
import type {
  PublicDemoLetter,
  PublicDemoRunResult,
  PublicDemoScenario,
  PublicDemoStrategy,
} from "@/lib/publicDemoTypes";

const LOADING_PHASES = [
  "Reading the scenario through the live parser…",
  "Spotting items worth a closer look…",
  "Choosing the strongest items to act on first…",
  "Drafting bureau-ready dispute letters…",
  "Building your 72-hour gameplan…",
] as const;

const SCENARIO_CATEGORY_ORDER: Record<string, number> = {
  general: 0,
  law_backed: 1,
  thin_file: 2,
};

function sortScenarios(list: PublicDemoScenario[]): PublicDemoScenario[] {
  return [...list].sort(
    (a, b) =>
      (SCENARIO_CATEGORY_ORDER[a.category ?? "general"] ?? 99) -
      (SCENARIO_CATEGORY_ORDER[b.category ?? "general"] ?? 99),
  );
}

const SUPPORT_EMAIL = (
  import.meta.env.VITE_PUBLIC_SUPPORT_EMAIL as string | undefined
)?.trim();

/** Single “slide” frame: presentation-style, one column. */
const slideShell =
  "mx-auto flex w-full max-w-6xl flex-col min-h-0 rounded-2xl border-2 border-white/[0.12] bg-lab-surface/85 p-6 shadow-2xl shadow-black/25 backdrop-blur-sm sm:p-8";

const slideBodyMax =
  "flex min-h-0 flex-1 flex-col md:max-h-[min(78vh,760px)] md:min-h-[min(320px,48vh)] md:overflow-hidden";

const innerSection =
  "rounded-lg border border-white/[0.06] bg-lab-bg/20 px-4 py-4 sm:px-5 sm:py-5";

const innerSectionDay =
  "rounded-lg border border-neutral-200/80 bg-neutral-50/90 px-4 py-4 sm:px-5 sm:py-5";

export type DemoSurfaceTheme = "night" | "day";

/** Longer copy for expanded priority detail. */
const REVIEW_TYPE_LABELS: Record<string, string> = {
  identity_verification: "Personal information to fix",
  account_ownership: "An account to confirm or dispute",
  duplicate_account: "Possible duplicate listing",
  negative_impact: "A negative mark to challenge",
  accuracy_verification: "Report details that may be wrong",
  unverifiable_information: "Information that’s hard to verify",
};

/** Short pill titles (click for full detail). */
const PRIORITY_PILL_SHORT: Record<string, string> = {
  identity_verification: "Personal info",
  account_ownership: "Account",
  duplicate_account: "Duplicate",
  negative_impact: "Negative mark",
  accuracy_verification: "Accuracy",
  unverifiable_information: "Hard to verify",
};

function priorityPillLabel(p: PublicDemoStrategy["perClaim"][number]): string {
  const rt = (p.reviewType || "").trim();
  if (rt && PRIORITY_PILL_SHORT[rt]) return PRIORITY_PILL_SHORT[rt];
  const s = (p.summary || "").trim();
  if (!s) return "Item";
  if (s.length <= 26) return s;
  return `${s.slice(0, 23).trim()}…`;
}

function priorityDetailText(p: PublicDemoStrategy["perClaim"][number]): string {
  const s = (p.summary || "").trim();
  if (s) return s;
  const rt = (p.reviewType || "").trim();
  if (rt && REVIEW_TYPE_LABELS[rt]) return REVIEW_TYPE_LABELS[rt];
  return "Something on your report worth acting on first.";
}

const slideMotion = {
  initial: { opacity: 0, x: 16 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -12 },
  transition: { duration: 0.28, ease: [0.22, 1, 0.36, 1] as const },
};

function DemoUnavailablePanel({
  copy,
  onRetry,
  embeddedOnHome,
  panelClassName,
  surfaceTheme = "night",
}: {
  copy: PublicDemoUnavailableCopy;
  onRetry: () => void;
  embeddedOnHome?: boolean;
  panelClassName?: string;
  surfaceTheme?: DemoSurfaceTheme;
}) {
  const day = surfaceTheme === "day";
  const fg = day ? "text-neutral-950" : "text-lab-text";
  const muted = day ? "text-neutral-600" : "text-lab-muted";
  const subtle = day ? "text-neutral-500" : "text-lab-subtle";
  const techBox = day
    ? "mx-auto mt-4 max-w-lg rounded-lg border border-neutral-200/90 bg-neutral-50 px-3 py-2 text-left text-xs leading-relaxed text-neutral-600"
    : "mx-auto mt-4 max-w-lg rounded-lg border border-white/[0.06] bg-lab-bg/50 px-3 py-2 text-left text-xs leading-relaxed text-lab-subtle";
  const defaultPanel = day
    ? "mt-8 rounded-2xl border border-neutral-200/90 bg-white px-6 py-10 text-center shadow-lg shadow-neutral-900/5"
    : "mt-8 rounded-2xl border border-white/[0.08] bg-lab-surface/80 px-6 py-10 text-center shadow-lg shadow-black/20";
  return (
    <div className={panelClassName ?? defaultPanel}>
      <p className={`text-lg font-semibold ${fg}`}>{copy.headline}</p>
      <p className={`mx-auto mt-3 max-w-md text-sm leading-relaxed ${muted}`}>{copy.body}</p>
      {copy.technicalNote ? (
        <p className={techBox}>
          <span className={`font-medium ${muted}`}>Server message: </span>
          {copy.technicalNote}
        </p>
      ) : null}
      {copy.showOperatorDetails ? (
        <details className="mx-auto mt-5 max-w-lg text-left">
          <summary
            className={
              day
                ? "cursor-pointer text-sm font-medium text-neutral-800 hover:text-neutral-950"
                : "cursor-pointer text-sm font-medium text-lab-accent hover:text-sky-300"
            }
          >
            For site operators (enable the live demo)
          </summary>
          <ul className={`mt-3 list-disc space-y-2 pl-5 text-xs leading-relaxed ${subtle}`}>
            <li>
              By default the API auto-creates a system demo user on first run (no{" "}
              <code className="text-violet-200/90">PUBLIC_DEMO_USER_ID</code> required). Optionally set{" "}
              <code className="text-violet-200/90">PUBLIC_DEMO_USER_ID</code> to pin a specific{" "}
              <code className="text-violet-200/90">users.id</code>. Production-like deploys also need{" "}
              <code className="text-violet-200/90">PUBLIC_DEMO_ENABLED=1</code>.
            </li>
            <li>
              Open{" "}
              <code className="text-violet-200/90">/api/system/customer-web-status</code> (same host as the
              API; use <code className="text-violet-200/90">/workflow-api</code> prefix if that is how the
              app is built) and check <code className="text-violet-200/90">publicDemo.ready</code> and{" "}
              <code className="text-violet-200/90">configError</code>.
            </li>
            <li>
              Deploy fixture PDFs: repo <code className="text-violet-200/90">samples/*.pdf</code> must
              exist on the API host (same paths as in code).
            </li>
            <li>
              If <code className="text-violet-200/90">PUBLIC_DEMO_SECRET</code> is set on the API, set
              matching <code className="text-violet-200/90">VITE_PUBLIC_DEMO_SECRET</code> in{" "}
              <code className="text-violet-200/90">web/.env.local</code> and rebuild the web app.
            </li>
            <li>See <code className="text-violet-200/90">.env.example</code> in the repo — section &quot;Public React demo&quot;.</li>
          </ul>
        </details>
      ) : null}
      <div className="mx-auto mt-8 flex max-w-sm flex-col items-stretch gap-3">
        <Link
          to={buildProgramSignupHref()}
          onClick={() => writeDemoProgramBridge({ source: "demo_unavailable" })}
          className={
            day
              ? "rounded-lg bg-neutral-950 py-3 text-center text-sm font-semibold text-white shadow-md shadow-neutral-900/15 hover:bg-neutral-800"
              : "rounded-lg bg-lab-accent py-3 text-center text-sm font-semibold text-white shadow-md shadow-lab-accent/20 hover:bg-sky-500"
          }
        >
          Continue with your account
        </Link>
        <button
          type="button"
          onClick={() => onRetry()}
          className={
            day
              ? "rounded-lg border border-neutral-200/90 py-3 text-sm font-medium text-neutral-950 hover:bg-neutral-50"
              : "rounded-lg border border-white/[0.12] py-3 text-sm font-medium text-lab-text hover:bg-white/[0.04]"
          }
        >
          Try again
        </button>
        {SUPPORT_EMAIL ? (
          <a
            href={`mailto:${SUPPORT_EMAIL}?subject=850%20Lab%20demo`}
            className={
              day
                ? "text-center text-sm font-medium text-neutral-700 hover:text-neutral-950"
                : "text-center text-sm font-medium text-lab-accent hover:text-sky-300"
            }
          >
            Contact us
          </a>
        ) : embeddedOnHome ? null : (
          <Link
            to="/"
            className={
              day
                ? "text-center text-sm font-medium text-neutral-500 hover:text-neutral-900"
                : "text-center text-sm font-medium text-lab-muted hover:text-lab-accent"
            }
          >
            Back to home
          </Link>
        )}
      </div>
    </div>
  );
}

export type PublicDemoInteractiveSectionProps = {
  onRunSuccess?: (result: PublicDemoRunResult) => void;
  embeddedOnHome?: boolean;
  /** `day` = white marketing shell (landing). Default `night` matches app dark UI. */
  surfaceTheme?: DemoSurfaceTheme;
};

type ResultsPane = "analysis" | "gameplan";

export function PublicDemoInteractiveSection({
  onRunSuccess,
  embeddedOnHome,
  surfaceTheme = "night",
}: PublicDemoInteractiveSectionProps) {
  const day = surfaceTheme === "day";
  const slideShellDay =
    "mx-auto flex w-full max-w-6xl flex-col min-h-0 rounded-2xl border border-neutral-200/90 bg-white p-6 shadow-[0_28px_80px_-36px_rgba(15,23,42,0.18)] sm:p-8";
  const shellClass = day ? slideShellDay : slideShell;
  const innerClass = day ? innerSectionDay : innerSection;
  const fg = day ? "text-neutral-950" : "text-lab-text";
  const muted = day ? "text-neutral-600" : "text-lab-muted";
  const subtle = day ? "text-neutral-500" : "text-lab-subtle";
  const primaryBtn = day
    ? "w-full rounded-xl bg-neutral-950 py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-neutral-900/15 outline-none transition-transform focus-visible:ring-2 focus-visible:ring-neutral-400/50 active:scale-[0.99] disabled:opacity-45"
    : "w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-xl shadow-lab-accent/25 outline-none transition-transform focus-visible:ring-2 focus-visible:ring-lab-accent/40 active:scale-[0.99] disabled:opacity-45";
  const linkAccent = day
    ? "font-medium text-neutral-800 underline-offset-2 hover:text-neutral-950 hover:underline"
    : "font-medium text-lab-accent hover:text-sky-300";
  const [scenarios, setScenarios] = useState<PublicDemoScenario[]>([]);
  const [demoUnavailable, setDemoUnavailable] = useState<PublicDemoUnavailableCopy | null>(null);
  const [scenariosLoading, setScenariosLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<PublicDemoRunResult | null>(null);
  const [preview, setPreview] = useState<PublicDemoLetter | null>(null);
  const [stage, setStage] = useState<"welcome" | "running" | "results">("welcome");
  const [resultsPane, setResultsPane] = useState<ResultsPane>("analysis");
  const [expandedPriorityId, setExpandedPriorityId] = useState<string | null>(null);

  const loadScenarios = useCallback(async () => {
    setDemoUnavailable(null);
    setScenariosLoading(true);
    try {
      const s = sortScenarios(await fetchPublicDemoScenarios());
      setScenarios(s);
      setSelectedId((cur) => cur ?? (s[0]?.scenarioId ?? null));
    } catch (e) {
      setScenarios([]);
      setDemoUnavailable(classifyPublicDemoScenariosError(e));
    } finally {
      setScenariosLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadScenarios();
  }, [loadScenarios]);

  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(() => {
      setPhaseIdx((i) => (i + 1) % LOADING_PHASES.length);
    }, 2800);
    return () => window.clearInterval(t);
  }, [running]);

  useEffect(() => {
    if (result) {
      setResultsPane("analysis");
    }
  }, [result]);

  useEffect(() => {
    setExpandedPriorityId(null);
  }, [result?.workflowId]);

  const runDemo = useCallback(async () => {
    const sid = selectedId ?? scenarios[0]?.scenarioId;
    if (!sid) return;
    setRunning(true);
    setRunError(null);
    setResult(null);
    setPhaseIdx(0);
    setStage("running");
    try {
      const out = await runPublicDemoScenario(sid);
      setResult(out);
      setStage("results");
      onRunSuccess?.(out);
    } catch (e) {
      setRunError(e instanceof Error ? e.message : String(e));
      setStage("welcome");
    } finally {
      setRunning(false);
    }
  }, [selectedId, scenarios, onRunSuccess]);

  const resetToWelcome = useCallback(() => {
    setResult(null);
    setRunError(null);
    setStage("welcome");
    setResultsPane("analysis");
  }, []);

  const noScenariosPanel =
    !scenariosLoading && !demoUnavailable && scenarios.length === 0
      ? ({
          headline: "Sample PDFs missing on the server",
          body: "The API accepted the demo but returned no scenarios — usually the fixture files are not on disk at samples/ on the API host.",
          technicalNote: "Empty scenario list after successful HTTP response.",
          code: "PUBLIC_DEMO_NO_FIXTURES",
          showOperatorDetails: import.meta.env.VITE_HIDE_DEMO_OPS_HINTS !== "1",
        } satisfies PublicDemoUnavailableCopy)
      : null;

  const showStartControls =
    !scenariosLoading &&
    scenarios.length > 0 &&
    !demoUnavailable &&
    stage === "welcome";

  const demoView: "pick" | "loading" | "results" =
    stage === "results" && result ? "results" : stage === "running" || running ? "loading" : "pick";

  return (
    <section
      id="live-demo"
      data-testid="live-demo-section"
      className="relative scroll-mt-28"
      aria-label="Interactive scenario demo"
    >
      {!day ? (
        <div
          className="pointer-events-none absolute left-1/2 top-[20%] z-0 h-[min(70vw,420px)] w-[min(70vw,420px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.07] blur-[100px]"
          aria-hidden
        />
      ) : (
        <div
          className="pointer-events-none absolute left-1/2 top-[18%] z-0 h-[min(72vw,440px)] w-[min(72vw,440px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-br from-neutral-200/30 to-transparent blur-[90px]"
          aria-hidden
        />
      )}

      <div className="relative z-10 mx-auto w-full max-w-6xl px-0 sm:px-2">
        {embeddedOnHome ? (
          <>
            <h2 className="sr-only">Interactive scenario demo</h2>
            <span data-testid="demo-preview-badge" className="sr-only">
              Demo preview
            </span>
            <span data-testid="demo-headline" className="sr-only">
              Sample PDFs only — same member engine, not your upload.
            </span>
          </>
        ) : (
          <div className="flex flex-col items-center gap-4 text-center">
            <span
              data-testid="demo-preview-badge"
              className="inline-block rounded-full border border-white/10 bg-white/[0.05] px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.15em] text-lab-muted"
            >
              Demo preview
            </span>
            <h2
              data-testid="demo-headline"
              className="text-balance text-2xl font-semibold leading-tight tracking-tight text-lab-text sm:text-3xl md:text-4xl"
            >
              Run a real scenario in seconds
            </h2>
            <p
              data-testid="demo-subheadline"
              className="max-w-xl text-pretty text-sm leading-relaxed text-lab-muted sm:text-[15px]"
            >
              Three everyday situations people run into — same engine as members. Parsing, prioritization,
              bureau letters, and a 72-hour gameplan. Your own file is never uploaded here.
            </p>
          </div>
        )}

        <div className={embeddedOnHome ? "mt-0 md:mt-1" : "mt-8 md:mt-10"}>
          <div data-testid="demo-slide-deck" className={`${shellClass} ${slideBodyMax}`}>
            <h3 className={`shrink-0 text-center text-lg font-semibold sm:text-xl ${fg}`}>
              Start the demo
            </h3>

            <div className="relative mt-4 min-h-0 flex-1 overflow-hidden">
              <AnimatePresence mode="wait">
                {demoView === "pick" ? (
                  <motion.div
                    key="slide-pick"
                    className="flex h-full min-h-0 flex-col overflow-y-auto overscroll-contain pr-1"
                    {...slideMotion}
                  >
                    {demoUnavailable ? (
                      <DemoUnavailablePanel
                        copy={demoUnavailable}
                        onRetry={() => void loadScenarios()}
                        embeddedOnHome={embeddedOnHome}
                        surfaceTheme={surfaceTheme}
                        panelClassName={
                          day
                            ? "mt-2 rounded-xl border border-neutral-200/90 bg-neutral-50 px-4 py-6 text-center"
                            : "mt-2 rounded-xl border border-white/[0.06] bg-lab-bg/30 px-4 py-6 text-center"
                        }
                      />
                    ) : null}

                    {noScenariosPanel && !demoUnavailable ? (
                      <DemoUnavailablePanel
                        copy={noScenariosPanel}
                        onRetry={() => void loadScenarios()}
                        embeddedOnHome={embeddedOnHome}
                        surfaceTheme={surfaceTheme}
                        panelClassName={
                          day
                            ? "mt-2 rounded-xl border border-neutral-200/90 bg-neutral-50 px-4 py-6 text-center"
                            : "mt-2 rounded-xl border border-white/[0.06] bg-lab-bg/30 px-4 py-6 text-center"
                        }
                      />
                    ) : null}

                    {scenariosLoading ? (
                      <p className={`mt-6 text-center text-sm ${muted}`} role="status">
                        Loading scenarios…
                      </p>
                    ) : null}

                    {showStartControls ? (
                      <div className="mt-4 flex flex-col gap-5">
                        <button
                          type="button"
                          data-testid="demo-generate-preview-button"
                          onClick={() => void runDemo()}
                          disabled={running}
                          className={primaryBtn}
                        >
                          Generate demo preview
                        </button>

                        <div>
                          <p className={`mb-3 text-center text-xs font-medium uppercase tracking-wide ${subtle}`}>
                            Choose a scenario
                          </p>
                          <div
                            data-testid="demo-scenario-list"
                            className="grid grid-cols-1 gap-3 sm:grid-cols-3"
                            role="radiogroup"
                            aria-label="Demo scenario"
                          >
                            {scenarios.map((s) => {
                              const selected = selectedId === s.scenarioId;
                              return (
                                <label
                                  key={s.scenarioId}
                                  className={`flex cursor-pointer flex-col rounded-xl border p-3 text-left transition-colors focus-within:ring-2 ${
                                    day
                                      ? selected
                                        ? "border-neutral-400 bg-neutral-100 ring-1 ring-neutral-300/80 focus-within:ring-neutral-400/50"
                                        : "border-neutral-200/90 bg-white hover:border-neutral-300 focus-within:ring-neutral-400/40"
                                      : `bg-lab-bg/25 focus-within:ring-lab-accent/40 ${
                                          selected
                                            ? "border-lab-accent/50 bg-lab-accent/10 ring-1 ring-lab-accent/35"
                                            : "border-white/[0.08] hover:border-white/[0.14]"
                                        }`
                                  }`}
                                >
                                  <input
                                    type="radio"
                                    name="demo-scenario-home"
                                    className="sr-only"
                                    checked={selected}
                                    onChange={() => setSelectedId(s.scenarioId)}
                                  />
                                  {s.categoryLabel ? (
                                    <span
                                      className={`mb-2 inline-block w-fit rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                                        day
                                          ? "border-neutral-200/90 bg-neutral-100 text-neutral-500"
                                          : "border-white/[0.1] bg-white/[0.04] text-lab-subtle"
                                      }`}
                                    >
                                      {s.categoryLabel}
                                    </span>
                                  ) : null}
                                  <span className={`text-sm font-semibold leading-snug ${fg}`}>
                                    {s.title}
                                  </span>
                                  <p className={`mt-2 flex-1 text-xs leading-relaxed ${muted}`}>
                                    {s.description}
                                  </p>
                                </label>
                              );
                            })}
                          </div>
                        </div>

                        {runError ? (
                          <div
                            className={
                              day
                                ? "rounded-xl border border-red-200/90 bg-red-50 px-4 py-4 text-center"
                                : "rounded-xl border border-red-400/20 bg-red-500/10 px-4 py-4 text-center"
                            }
                          >
                            <p className={`text-sm font-medium ${fg}`}>Couldn&apos;t finish this run</p>
                            <p className={`mt-2 text-sm ${muted}`}>
                              Try again in a moment. If it keeps happening, use the form below and we&apos;ll
                              help.
                            </p>
                            <button
                              type="button"
                              onClick={() => {
                                setRunError(null);
                                void runDemo();
                              }}
                              className={`mt-4 text-sm font-medium ${day ? "text-neutral-900 underline-offset-2 hover:underline" : "text-lab-accent hover:text-sky-300"}`}
                            >
                              Try again
                            </button>
                          </div>
                        ) : null}
                      </div>
                    ) : null}

                    {import.meta.env.DEV &&
                    !scenariosLoading &&
                    scenarios.length > 0 &&
                    !demoUnavailable ? (
                      <p
                        className={`mt-4 text-center text-[10px] leading-snug ${day ? "text-neutral-400" : "text-lab-subtle/70"}`}
                        title="Scenario titles come from this server. If copy looks old, this URL is not your updated API or repo."
                      >
                        Dev: scenarios from <span className="font-mono">{workflowApiBase()}</span>
                      </p>
                    ) : null}

                  </motion.div>
                ) : null}

                {demoView === "loading" ? (
                  <motion.div
                    key="slide-loading"
                    className="flex h-full min-h-[280px] flex-col items-center justify-center py-8"
                    {...slideMotion}
                  >
                    <div
                      className={
                        day
                          ? "h-14 w-14 animate-pulse rounded-full border-2 border-neutral-200 border-t-neutral-800"
                          : "h-14 w-14 animate-pulse rounded-full border-2 border-lab-accent/30 border-t-lab-accent"
                      }
                      aria-hidden
                    />
                    <AnimatePresence mode="wait">
                      <motion.p
                        key={phaseIdx}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                        className={`mt-10 max-w-md px-4 text-center text-sm leading-relaxed ${muted}`}
                      >
                        {LOADING_PHASES[phaseIdx]}
                      </motion.p>
                    </AnimatePresence>
                    <p className={`mt-4 max-w-sm px-4 text-center text-xs ${subtle}`}>
                      Your results and gameplan will appear on the next step — usually under a minute.
                    </p>
                  </motion.div>
                ) : null}

                {demoView === "results" && result ? (
                  <motion.div
                    key="slide-results"
                    className="flex h-full min-h-0 flex-col"
                    {...slideMotion}
                  >
                    <div className="flex shrink-0 flex-col items-center gap-2 sm:flex-row sm:justify-center sm:gap-3">
                      <span className={`text-[10px] font-medium uppercase tracking-wider ${subtle}`}>
                        View
                      </span>
                      <div
                        className={
                          day
                            ? "inline-flex rounded-lg border border-neutral-200/90 bg-neutral-100/80 p-0.5"
                            : "inline-flex rounded-lg border border-white/[0.08] bg-lab-bg/30 p-0.5"
                        }
                        role="tablist"
                        aria-label="Results view"
                      >
                        <button
                          type="button"
                          role="tab"
                          aria-selected={resultsPane === "analysis"}
                          data-testid="demo-results-tab-analysis"
                          onClick={() => setResultsPane("analysis")}
                          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                            resultsPane === "analysis"
                              ? day
                                ? "bg-white text-neutral-950 shadow-sm"
                                : "bg-white/[0.08] text-lab-text"
                              : day
                                ? "text-neutral-600 hover:text-neutral-950"
                                : "text-lab-muted hover:text-lab-text"
                          }`}
                        >
                          Analysis
                        </button>
                        <button
                          type="button"
                          role="tab"
                          aria-selected={resultsPane === "gameplan"}
                          data-testid="demo-results-tab-gameplan"
                          onClick={() => setResultsPane("gameplan")}
                          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                            resultsPane === "gameplan"
                              ? day
                                ? "bg-white text-neutral-950 shadow-sm"
                                : "bg-white/[0.08] text-lab-text"
                              : day
                                ? "text-neutral-600 hover:text-neutral-950"
                                : "text-lab-muted hover:text-lab-text"
                          }`}
                        >
                          Gameplan
                        </button>
                      </div>
                    </div>

                    <div className="mt-4 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1">
                      {resultsPane === "analysis" ? (
                        <div data-testid="demo-results-analysis-pane">
                          <p
                            className={
                              day
                                ? "text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-600"
                                : "text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-400/90"
                            }
                          >
                            Analysis &amp; findings
                          </p>
                          {result.partial ? (
                            <p
                              className={
                                day
                                  ? "mt-2 rounded-lg border border-amber-200/80 bg-amber-50 px-3 py-2 text-xs text-amber-900/90"
                                  : "mt-2 rounded-lg border border-amber-400/25 bg-amber-500/10 px-3 py-2 text-xs text-amber-100/90"
                              }
                            >
                              Partial output (e.g. letters or payment step) — still from the live pipeline.
                            </p>
                          ) : null}
                          <div className="mt-4 grid grid-cols-1 gap-5 lg:grid-cols-2 lg:gap-6">
                            <div className="min-w-0 space-y-4">
                              <section className={innerClass}>
                                <h4 className={`text-sm font-semibold ${fg}`}>What showed up on the report</h4>
                                <p className={`mt-1 text-[11px] ${subtle}`}>
                                  {result.scenarioTitle || result.scenarioId}
                                </p>
                                {result.message ? (
                                  <p className={day ? "mt-2 text-sm text-amber-800" : "mt-2 text-sm text-amber-200/90"}>
                                    {result.message}
                                  </p>
                                ) : null}
                                {result.intake ? (
                                  <ul className={`mt-3 space-y-2 text-sm ${muted}`}>
                                    <li>
                                      <span className={`font-medium ${fg}`}>
                                        {result.intake.aggregates.reportCount}
                                      </span>{" "}
                                      bureau report(s) ·{" "}
                                      <span className={`font-medium ${fg}`}>
                                        {result.intake.reviewClaimsCount}
                                      </span>{" "}
                                      items for review
                                    </li>
                                    <li>
                                      Accounts referenced:{" "}
                                      <span className={`font-medium ${fg}`}>
                                        {result.intake.aggregates.totalAccountsExtracted}
                                      </span>
                                    </li>
                                  </ul>
                                ) : null}
                              </section>
                              {result.strategy ? (
                                <section className={innerClass}>
                                  <h4 className={`text-sm font-semibold ${fg}`}>What we&apos;d tackle first</h4>
                                  <p className={`mt-2 text-sm leading-relaxed ${muted}`}>
                                    {result.strategy.roundSummary || result.strategy.rationale}
                                  </p>
                                  {result.strategy.perClaim.length ? (
                                    <div
                                      className={`mt-4 border-t pt-3 ${day ? "border-neutral-200/80" : "border-white/[0.06]"}`}
                                    >
                                      <p className={`text-[11px] ${subtle}`}>
                                        Tap a tag for more on why it&apos;s prioritized.
                                      </p>
                                      <div className="mt-2 flex flex-wrap gap-2">
                                        {result.strategy.perClaim.slice(0, 12).map((p) => {
                                          const open = expandedPriorityId === p.reviewClaimId;
                                          return (
                                            <button
                                              key={p.reviewClaimId}
                                              type="button"
                                              data-testid={`demo-priority-pill-${p.reviewClaimId}`}
                                              aria-expanded={open}
                                              aria-controls={`demo-priority-detail-${p.reviewClaimId}`}
                                              id={`demo-priority-trigger-${p.reviewClaimId}`}
                                              onClick={() =>
                                                setExpandedPriorityId((cur) =>
                                                  cur === p.reviewClaimId ? null : p.reviewClaimId,
                                                )
                                              }
                                              className={`rounded-full border px-3 py-1.5 text-left text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 ${
                                                day
                                                  ? open
                                                    ? "border-neutral-400 bg-neutral-200/80 text-neutral-950 focus-visible:ring-neutral-400/50"
                                                    : "border-neutral-200/90 bg-white text-neutral-600 hover:border-neutral-300 hover:text-neutral-950 focus-visible:ring-neutral-400/40"
                                                  : open
                                                    ? "border-lab-accent/60 bg-lab-accent/15 text-lab-text focus-visible:ring-lab-accent/40"
                                                    : "border-white/[0.12] bg-lab-bg/30 text-lab-muted hover:border-white/[0.2] hover:text-lab-text focus-visible:ring-lab-accent/40"
                                              }`}
                                            >
                                              {priorityPillLabel(p)}
                                            </button>
                                          );
                                        })}
                                      </div>
                                      {expandedPriorityId ? (
                                        <div
                                          id={`demo-priority-detail-${expandedPriorityId}`}
                                          role="region"
                                          aria-labelledby={`demo-priority-trigger-${expandedPriorityId}`}
                                          className={
                                            day
                                              ? "mt-3 rounded-lg border border-neutral-200/90 bg-neutral-50 px-3 py-3"
                                              : "mt-3 rounded-lg border border-white/[0.08] bg-lab-bg/25 px-3 py-3"
                                          }
                                        >
                                          {(() => {
                                            const p = result.strategy?.perClaim.find(
                                              (x) => x.reviewClaimId === expandedPriorityId,
                                            );
                                            if (!p) return null;
                                            return (
                                              <p className={`text-sm leading-relaxed ${fg}`}>
                                                {priorityDetailText(p)}
                                              </p>
                                            );
                                          })()}
                                        </div>
                                      ) : null}
                                    </div>
                                  ) : null}
                                </section>
                              ) : null}
                            </div>
                            <div className="min-w-0">
                              <PublicDemoBureauLetterStrip
                                letters={result.letters}
                                onOpen={(L) => setPreview(L)}
                                variant={day ? "light" : "dark"}
                              />
                              {result.letterGenerationNote ? (
                                <p className={day ? "mt-3 text-xs text-amber-800/90" : "mt-3 text-xs text-amber-200/85"}>
                                  {result.letterGenerationNote}
                                </p>
                              ) : null}
                            </div>
                          </div>
                          <button
                            type="button"
                            data-testid="demo-next-gameplan-button"
                            onClick={() => setResultsPane("gameplan")}
                            className={
                              day
                                ? "mt-6 w-full rounded-xl bg-neutral-950 py-3 text-sm font-semibold text-white shadow-lg shadow-neutral-900/15 sm:w-auto sm:min-w-[240px]"
                                : "mt-6 w-full rounded-xl bg-lab-accent py-3 text-sm font-semibold text-white shadow-lg shadow-lab-accent/20 sm:w-auto sm:min-w-[240px]"
                            }
                          >
                            Next: 72-hour gameplan
                          </button>
                          <p className={`mt-4 text-center text-xs leading-relaxed ${muted}`}>
                            When you&apos;re ready,{" "}
                            <strong className={`font-medium ${fg}`}>tell us who you are below</strong>.
                          </p>
                        </div>
                      ) : (
                        <div data-testid="demo-results-gameplan-pane" className="flex min-h-0 flex-col">
                          <button
                            type="button"
                            data-testid="demo-back-analysis-button"
                            onClick={() => setResultsPane("analysis")}
                            className={linkAccent + " mb-4 self-start text-sm"}
                          >
                            Back to analysis
                          </button>
                          <p
                            className={
                              day
                                ? "text-[10px] font-semibold uppercase tracking-[0.12em] text-neutral-600"
                                : "text-[10px] font-semibold uppercase tracking-[0.12em] text-emerald-400/90"
                            }
                          >
                            72-hour gameplan
                          </p>
                          <div
                            className="mt-3 min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain pr-1"
                            data-testid="demo-preview-filled"
                          >
                            {result.creditCommandPlan ? (
                              <CreditCommandPlanSection
                                plan={result.creditCommandPlan}
                                layout="publicDemoExpandable"
                                scenarioHeadline={result.scenarioTitle || result.scenarioId}
                                surfaceLight={day}
                              />
                            ) : (
                              <p className={`text-sm ${muted}`}>
                                No gameplan returned for this run — try again or continue with your account.
                              </p>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    <div
                      className={`mt-4 flex shrink-0 flex-wrap items-center justify-center gap-x-2 gap-y-2 border-t pt-4 text-sm ${
                        day ? "border-neutral-200/80" : "border-white/[0.08]"
                      }`}
                      data-testid="demo-start-card-results"
                    >
                      <button
                        type="button"
                        onClick={resetToWelcome}
                        className={day ? "font-semibold text-neutral-800 hover:text-neutral-950" : "font-medium text-lab-accent hover:text-sky-300"}
                      >
                        Try another scenario
                      </button>
                      <span className={day ? "text-neutral-400/80" : "text-lab-subtle/80"} aria-hidden>
                        ·
                      </span>
                      <button
                        type="button"
                        data-testid="demo-run-again-button"
                        onClick={() => void runDemo()}
                        disabled={running}
                        className={
                          day
                            ? `${muted} underline-offset-2 hover:text-neutral-950 hover:underline disabled:opacity-45`
                            : "text-lab-muted underline-offset-2 hover:text-lab-accent hover:underline disabled:opacity-45"
                        }
                      >
                        Run again with selected scenario
                      </button>
                    </div>
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </div>

      <LetterPreviewModal
        open={preview !== null}
        onClose={() => setPreview(null)}
        bureau={preview?.bureauDisplay || preview?.bureau || ""}
        body={preview?.body || ""}
        loading={false}
      />
    </section>
  );
}
