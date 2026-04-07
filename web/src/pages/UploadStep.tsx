import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { GetReportPanel } from "@/components/GetReportPanel";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { UploadDropzoneCard } from "@/components/UploadDropzoneCard";
import {
  isWorkflowReportUploadAbortError,
  pollReportUploadParseJob,
  postReportUpload,
} from "@/lib/workflowApi";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const page = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.07, delayChildren: 0.05 },
  },
};

const block = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

function skipReasonMessage(reason: string): string {
  switch (reason) {
    case "no_text":
      return "We could not read text from this PDF. Try another export or a clearer scan.";
    case "unknown":
      return "We could not confirm this is an Equifax, Experian, or TransUnion report.";
    case "3bureau":
      return "Combined 3-bureau PDFs are not supported. Upload one bureau at a time.";
    case "pdf_merge_failed":
      return "We could not merge those PDF parts. Make sure each part is a valid PDF from the same export, in page order.";
    case "pdf_split_failed":
      return "We could not split that PDF into processable pieces. Try re-exporting from the bureau, or split it into smaller PDFs under 25 MB each.";
    default:
      return `This file could not be processed (${reason}).`;
  }
}

export function UploadStep() {
  const navigate = useNavigate();
  const location = useLocation();
  const [getReportOpen, setGetReportOpen] = useState(false);
  const [privacyAgreed, setPrivacyAgreed] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [uploadParseError, setUploadParseError] = useState<string | null>(null);
  const [parseJob, setParseJob] = useState<{
    jobId: string;
    workflowId: string;
  } | null>(null);
  const [dropzoneResetKey, setDropzoneResetKey] = useState(0);
  const pendingUploadFilesRef = useRef<File[] | null>(null);
  const parsePollGenerationRef = useRef(0);
  const initOnceRef = useRef(false);
  const { token: authToken, emailVerified } = useAuth();
  const {
    token,
    workflowId,
    loading: wfLoading,
    authoritativeStepId,
    applyWorkflowEnvelope,
    initWorkflow,
  } = useCustomerWorkflow();

  const authReturn = encodeURIComponent(`${location.pathname}${location.search}`);

  useEffect(() => {
    if (!authToken || !emailVerified || workflowId || wfLoading) return;
    if (initOnceRef.current) return;
    initOnceRef.current = true;
    void (async () => {
      try {
        setSetupError(null);
        await initWorkflow();
      } catch (e) {
        initOnceRef.current = false;
        setSetupError(
          e instanceof Error ? e.message : "Could not start your workspace.",
        );
      }
    })();
  }, [authToken, emailVerified, workflowId, wfLoading, initWorkflow]);

  const guestExplore = !authToken;
  const workspaceReady = Boolean(
    authToken && emailVerified && workflowId && !wfLoading,
  );
  const allowUpload = workspaceReady && privacyAgreed;
  const parseBusy = parseJob != null;

  useEffect(() => {
    if (!token || !parseJob) return;
    const runId = ++parsePollGenerationRef.current;
    const ac = new AbortController();
    void (async () => {
      try {
        const final = await pollReportUploadParseJob(
          token,
          parseJob.workflowId,
          parseJob.jobId,
          { signal: ac.signal },
        );
        if (runId !== parsePollGenerationRef.current) return;
        const filesForNav = pendingUploadFilesRef.current;
        setParseJob(null);
        pendingUploadFilesRef.current = null;
        applyWorkflowEnvelope(final.workflow);
        if (!final.ok) {
          const first = final.fileSkips[0];
          const msg = first
            ? skipReasonMessage(first.reason)
            : final.workflow.userMessage || "Upload could not be completed.";
          setUploadParseError(msg);
          setDropzoneResetKey((k) => k + 1);
          return;
        }
        const nameHint =
          filesForNav && filesForNav.length > 0
            ? filesForNav.length === 1
              ? filesForNav[0].name
              : `${filesForNav.length} merged parts`
            : "your report";
        navigate("/analyze", {
          replace: true,
          state: { uploadedReportFileName: nameHint },
        });
      } catch (e) {
        if (isWorkflowReportUploadAbortError(e)) return;
        if (runId !== parsePollGenerationRef.current) return;
        setUploadParseError(e instanceof Error ? e.message : "Report processing failed");
        setParseJob(null);
        pendingUploadFilesRef.current = null;
        setDropzoneResetKey((k) => k + 1);
      }
    })();
    return () => {
      ac.abort();
    };
  }, [token, parseJob?.jobId, parseJob?.workflowId, applyWorkflowEnvelope, navigate]);

  const onUploadPdfs = useCallback(
    async (files: File[]) => {
      if (!token || !workflowId) {
        return {
          success: false as const,
          message:
            "Sign in and create a free account to upload your report and save progress.",
        };
      }
      setUploadParseError(null);
      try {
        const r = await postReportUpload(token, workflowId, files, privacyAgreed);
        applyWorkflowEnvelope(r.workflow);
        if (r.processing && r.jobId) {
          pendingUploadFilesRef.current = files;
          setParseJob({ jobId: r.jobId, workflowId });
          return { success: true as const };
        }
        if (!r.ok) {
          const first = r.fileSkips[0];
          const msg = first
            ? skipReasonMessage(first.reason)
            : r.workflow.userMessage || "Upload could not be completed.";
          return { success: false as const, message: msg };
        }
        navigate("/analyze", {
          replace: true,
          state: {
            uploadedReportFileName:
              files.length === 1 ? files[0].name : `${files.length} merged parts`,
          },
        });
        return { success: true as const };
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        return { success: false as const, message: msg };
      }
    },
    [token, workflowId, privacyAgreed, applyWorkflowEnvelope, navigate],
  );

  const isAddAnother = authoritativeStepId === "review_claims";

  return (
    <div className="relative flex min-h-[100dvh] flex-col bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[28%] z-0 h-[min(90vw,560px)] w-[min(90vw,560px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.1] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute bottom-[15%] right-[-10%] z-0 h-[min(60vw,320px)] w-[min(60vw,320px)] rounded-full bg-sky-500/[0.05] blur-[90px]"
        aria-hidden
      />

      <GetReportPanel open={getReportOpen} onClose={() => setGetReportOpen(false)} />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto flex w-full max-w-xl flex-1 flex-col justify-center px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-[calc(3.5rem+0.35rem)] sm:max-w-2xl sm:px-6 sm:pb-4 sm:pt-[calc(3.5rem+0.5rem)]">
        <motion.div className="flex w-full flex-col items-center" variants={page} initial="hidden" animate="show">
          {guestExplore ? (
            <motion.div
              variants={block}
              className="mb-3 w-full rounded-xl border border-sky-400/20 bg-gradient-to-b from-sky-500/15 to-lab-surface/40 px-4 py-3 text-left shadow-lg shadow-black/20 sm:mb-4"
            >
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-sky-300/90">Account required</p>
              <p className="mt-2 text-sm font-medium text-lab-text">Your program is waiting on an account</p>
              <p className="mt-1 text-sm leading-relaxed text-lab-muted">
                Create a free account to save upload → findings → letters in one path.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link
                  to={`/signup?next=${authReturn}`}
                  state={{ from: location.pathname }}
                  className="inline-flex rounded-xl bg-lab-accent px-4 py-2.5 text-sm font-bold text-white shadow-md shadow-lab-accent/25 hover:brightness-110"
                >
                  Create account
                </Link>
                <Link
                  to={`/login?next=${authReturn}`}
                  state={{ from: location.pathname }}
                  className="inline-flex items-center rounded-xl border border-white/15 px-4 py-2.5 text-sm font-semibold text-lab-text hover:bg-white/[0.04]"
                >
                  Sign in
                </Link>
              </div>
            </motion.div>
          ) : null}

          {setupError ? (
            <motion.p
              variants={block}
              className="mb-2 w-full rounded-lg border border-red-500/35 bg-red-500/10 px-3 py-2 text-center text-sm text-red-100/95"
            >
              {setupError}
            </motion.p>
          ) : null}

          {uploadParseError ? (
            <motion.p
              variants={block}
              className="mb-2 w-full rounded-lg border border-red-500/35 bg-red-500/10 px-3 py-2 text-center text-sm text-red-100/95"
            >
              {uploadParseError}
            </motion.p>
          ) : null}

          {parseBusy ? (
            <motion.div
              variants={block}
              className="mb-2 w-full rounded-lg border border-sky-500/35 bg-sky-500/10 px-3 py-2 text-center text-sm text-sky-100"
              role="status"
              aria-live="polite"
            >
              Processing your report… This can take a minute for large files. You can stay on this
              page.
            </motion.div>
          ) : null}

          {!guestExplore && authToken && emailVerified && !workflowId && wfLoading ? (
            <motion.p variants={block} className="mb-2 text-center text-sm font-medium text-lab-muted">
              Starting your program workspace…
            </motion.p>
          ) : null}

          <motion.div
            variants={block}
            className="w-full rounded-2xl border border-white/[0.1] bg-lab-surface/45 p-4 shadow-[0_28px_90px_-36px_rgba(0,0,0,0.65)] backdrop-blur-md sm:p-5"
          >
            <div className="text-center">
              <span className="inline-flex rounded-full border border-lab-accent/25 bg-lab-accent/[0.1] px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.18em] text-lab-accent sm:px-3 sm:py-1 sm:text-[10px] sm:tracking-[0.2em]">
                {isAddAnother ? "Add report" : "Step · Upload"}
              </span>
              <h1 className="mt-2 text-balance text-xl font-bold leading-snug tracking-tight text-lab-text sm:mt-2.5 sm:text-2xl sm:leading-tight">
                {isAddAnother ? "Add another bureau PDF" : "Upload your bureau report"}
              </h1>
              <p className="mx-auto mt-1.5 max-w-md text-pretty text-xs font-medium leading-snug text-lab-muted sm:mt-2 sm:text-sm sm:leading-relaxed">
                {isAddAnother ? (
                  <>
                    We&apos;ll parse and refresh your findings. When you&apos;re done adding files, open{" "}
                    <span className="font-bold text-lab-text">Findings</span> and tap{" "}
                    <span className="font-bold text-lab-text">Begin review</span>.
                  </>
                ) : (
                  <>
                    Everything below becomes <span className="font-bold text-lab-text">one report</span> for this
                    round — then findings, review, strategy, same engine end to end.
                  </>
                )}
              </p>
            </div>

            {!isAddAnother ? (
              <div className="mt-3 grid gap-2 sm:grid-cols-2 sm:mt-3.5">
                <div className="rounded-lg border border-white/[0.08] bg-gradient-to-br from-lab-accent/[0.07] to-transparent px-3 py-2 text-left sm:px-3.5 sm:py-2.5">
                  <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-lab-accent sm:text-[10px]">Path A</p>
                  <p className="mt-0.5 text-xs font-bold text-lab-text sm:text-sm">One big PDF</p>
                  <p className="mt-0.5 text-[11px] leading-snug text-lab-muted sm:text-xs">Up to 200 MB. Split, merge, parse.</p>
                </div>
                <div className="rounded-lg border border-white/[0.08] bg-white/[0.02] px-3 py-2 text-left sm:px-3.5 sm:py-2.5">
                  <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-lab-muted sm:text-[10px]">Path B</p>
                  <p className="mt-0.5 text-xs font-bold text-lab-text sm:text-sm">Multiple parts</p>
                  <p className="mt-0.5 text-[11px] leading-snug text-lab-muted sm:text-xs">Each ≤25 MB. Combine, then parse.</p>
                </div>
              </div>
            ) : null}

            <label
              className={`mt-3 flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2 text-left transition-colors sm:mt-3.5 sm:gap-3 sm:px-3.5 sm:py-2.5 ${
                guestExplore
                  ? "cursor-not-allowed border-white/[0.05] opacity-50"
                  : privacyAgreed
                    ? "border-lab-accent/30 bg-lab-accent/[0.06]"
                    : "border-white/[0.08] bg-black/15 hover:border-white/[0.12]"
              }`}
            >
              <input
                type="checkbox"
                disabled={guestExplore}
                className="mt-0.5 h-4 w-4 shrink-0 rounded border-white/25 bg-lab-surface text-lab-accent focus:ring-lab-accent/50 disabled:opacity-50"
                checked={privacyAgreed}
                onChange={(e) => setPrivacyAgreed(e.target.checked)}
              />
              <span className="text-xs font-medium leading-snug text-lab-muted sm:text-sm">
                I agree to secure processing of my credit report data (same terms as the main 850 Lab
                experience).
              </span>
            </label>

            <div className="mt-3 sm:mt-3.5">
              <UploadDropzoneCard
                key={dropzoneResetKey}
                disabled={!allowUpload || parseBusy}
                onUploadPdfs={onUploadPdfs}
              />
            </div>

            <div className="mt-3 flex flex-col items-center gap-1 border-t border-white/[0.06] pt-3 text-center sm:mt-3.5 sm:gap-1.5 sm:pt-3.5">
              <Link
                to="/get-report"
                className="text-xs font-semibold text-lab-accent hover:text-sky-300 sm:text-sm"
              >
                Need a report first? Get your credit report
              </Link>
              <button
                type="button"
                onClick={() => setGetReportOpen(true)}
                className="text-[11px] font-medium text-lab-subtle transition-colors hover:text-lab-muted"
              >
                Don&apos;t have your report yet?
              </button>
              <p className="max-w-sm pt-1 text-center text-[10px] leading-snug text-lab-subtle/90 sm:text-[11px]">
                Bureau PDF required — no upload-free path in the web app yet.
              </p>
            </div>
          </motion.div>
        </motion.div>
      </main>
    </div>
  );
}
