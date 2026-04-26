import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { GetReportPanel } from "@/components/GetReportPanel";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { UploadDropzoneCard } from "@/components/UploadDropzoneCard";
import {
  isWorkflowReportUploadAbortError,
  pollReportUploadParseJob,
  postReportUpload,
} from "@/lib/workflowApi";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  stepChildVariants as block,
  stepPageVariants as page,
} from "@/lib/motionStep";
import { TRUST_SIGNALS_BEFORE_UPLOAD } from "@/lib/flowMicrocopy";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";

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
      return "We could not split that PDF into smaller sections. Try re-exporting from the bureau, or split it into smaller PDFs under 25 MB each.";
    default:
      return `We couldn’t organize this file for review (${reason}). Try another export.`;
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
    orionViewModel,
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
        applyWorkflowEnvelope({
          ...final.workflow,
          ...(final.workflowSync ? { workflowSync: final.workflowSync } : {}),
        });
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
        setUploadParseError(e instanceof Error ? e.message : "We couldn’t finish organizing your report.");
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
        applyWorkflowEnvelope({
          ...r.workflow,
          ...(r.workflowSync ? { workflowSync: r.workflowSync } : {}),
        });
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
    <div
      className="relative flex min-h-[100dvh] flex-col bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <GetReportPanel open={getReportOpen} onClose={() => setGetReportOpen(false)} />

      <TopBarMinimal />

      <StepMainColumn
        className={`relative z-10 mx-auto flex w-full max-w-xl flex-1 flex-col px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:max-w-2xl sm:px-6 sm:pb-6 ${stepMainColumnTopClass(!!workflowId, "upload")}`}
      >
        <motion.div className="flex w-full flex-col" variants={page} initial="hidden" animate="show">
          {guestExplore ? (
            <motion.div
              variants={block}
              className="mb-6 w-full rounded-xl border border-zinc-700/50 bg-gradient-to-b from-zinc-500/12 to-lab-surface/40 px-4 py-3 text-left shadow-lg shadow-black/20 sm:mb-8"
            >
              <p className="text-xs font-bold uppercase tracking-[0.14em] text-zinc-400/90">Account required</p>
              <p className="mt-2 text-sm font-medium text-lab-text">Your program is waiting on an account</p>
              <p className="mt-1 text-sm leading-relaxed text-lab-muted">
                Create a free account to save upload → findings → letters in one path.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Link
                  to={`/signup?next=${authReturn}`}
                  state={{ from: location.pathname }}
                  className="inline-flex rounded-xl bg-lab-accent px-4 py-2.5 text-sm font-bold text-white shadow-md shadow-black/35 hover:brightness-110"
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
              className="mb-4 w-full rounded-lg border border-red-500/35 bg-red-500/10 px-3 py-2 text-center text-sm text-red-100/95"
            >
              {setupError}
            </motion.p>
          ) : null}

          {uploadParseError ? (
            <motion.p
              variants={block}
              className="mb-4 w-full rounded-lg border border-red-500/35 bg-red-500/10 px-3 py-2 text-center text-sm text-red-100/95"
            >
              {uploadParseError}
            </motion.p>
          ) : null}

          {!guestExplore && authToken && emailVerified && !workflowId && wfLoading ? (
            <motion.p variants={block} className="mb-4 text-center text-sm font-medium text-lab-muted">
              Starting your program workspace…
            </motion.p>
          ) : null}

          <div className="flex w-full flex-col space-y-6 sm:space-y-8">
            {!isAddAnother ? (
              <motion.div variants={block} className="text-center">
                <h2 className="step-title mt-0 text-pretty leading-tight sm:leading-snug">
                  Get your report into 850 Lab
                </h2>
                <p className="step-support mx-auto mt-3 max-w-lg text-pretty">
                  Choose how you want to start — both paths stay in the same program.
                </p>
                <ul className="mx-auto mt-4 flex max-w-lg flex-wrap items-center justify-center gap-x-3 gap-y-1.5 text-[11px] font-medium text-lab-subtle sm:text-xs">
                  {TRUST_SIGNALS_BEFORE_UPLOAD.map((t) => (
                    <li
                      key={t}
                      className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.02] px-2.5 py-1"
                    >
                      <span className="h-1 w-1 rounded-full bg-emerald-400/80" aria-hidden />
                      {t}
                    </li>
                  ))}
                </ul>
              </motion.div>
            ) : (
              <motion.div variants={block} className="text-center">
                <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-lab-subtle">
                  Add a bureau
                </p>
                <h2 className="mt-3 text-balance text-2xl font-bold leading-tight text-lab-text sm:text-[1.65rem]">
                  Add another bureau PDF
                </h2>
                <p className="mx-auto mt-3 max-w-lg text-pretty text-sm text-lab-muted sm:text-[15px]">
                  We&apos;ll organize it with your file — then open{" "}
                  <span className="font-semibold text-lab-text">Findings</span> and tap{" "}
                  <span className="font-semibold text-lab-text">Begin review</span> when you&apos;re ready.
                </p>
              </motion.div>
            )}

            {!isAddAnother ? (
              <motion.div
                variants={block}
                className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5"
              >
                <div className="flex min-h-0 flex-col rounded-2xl border border-lab-accent/25 bg-lab-surface/50 p-4 shadow-[0_20px_70px_-32px_rgba(0,0,0,0.55)] backdrop-blur-md sm:p-5">
                  <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
                    I already have my report
                  </p>
                  <h3 className="mt-1.5 text-left text-base font-semibold text-lab-text sm:text-lg">
                    Upload my PDF
                  </h3>
                  <p className="mt-1.5 text-left text-sm leading-relaxed text-lab-muted">
                    One bureau at a time (or pick several files in the dialog). We parse it here — you
                    approve the next step.
                  </p>
                  <label
                    className={`mt-4 flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left transition-colors sm:gap-3 sm:px-3.5 sm:py-3 ${
                      guestExplore
                        ? "cursor-not-allowed border-white/[0.05] opacity-50"
                        : privacyAgreed
                          ? "border-zinc-600/40 bg-white/[0.03]"
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
                      I agree to secure handling of my credit report (850 Lab terms).
                    </span>
                  </label>
                  <div className="mt-4 min-h-0 flex-1">
                    <UploadDropzoneCard
                      key={dropzoneResetKey}
                      disabled={!allowUpload || parseBusy}
                      onUploadPdfs={onUploadPdfs}
                    />
                  </div>
                </div>

                <div className="flex flex-col rounded-2xl border border-white/[0.1] bg-lab-surface/35 p-4 shadow-[0_20px_70px_-32px_rgba(0,0,0,0.55)] backdrop-blur-md sm:p-5">
                  <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
                    I need my report first
                  </p>
                  <h3 className="mt-1.5 text-left text-base font-semibold text-lab-text sm:text-lg">
                    Get a bureau report
                  </h3>
                  <p className="mt-1.5 text-left text-sm leading-relaxed text-lab-muted">
                    Free annual reports or bureau panels — we&apos;ll bring you back here when you have
                    a PDF to upload.
                  </p>
                  <div className="mt-5 flex flex-1 flex-col justify-center gap-3 sm:mt-6">
                    <button
                      type="button"
                      onClick={() => setGetReportOpen(true)}
                      className="w-full rounded-xl border border-white/[0.12] bg-white/[0.06] py-3 text-sm font-semibold text-lab-text transition-colors hover:border-lab-accent/35 hover:bg-white/[0.1]"
                    >
                      Open get-report help
                    </button>
                    <Link
                      to="/get-report"
                      className="w-full rounded-xl border border-white/[0.08] py-3 text-center text-sm font-medium text-lab-muted transition-colors hover:border-white/[0.12] hover:text-lab-text"
                    >
                      All get-report options →
                    </Link>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div
                variants={block}
                className="w-full rounded-2xl border border-white/[0.1] bg-lab-surface/45 p-4 shadow-[0_28px_90px_-36px_rgba(0,0,0,0.65)] backdrop-blur-md sm:p-6"
              >
                <label
                  className={`flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left transition-colors sm:gap-3 sm:px-3.5 sm:py-3 ${
                    guestExplore
                      ? "cursor-not-allowed border-white/[0.05] opacity-50"
                      : privacyAgreed
                        ? "border-zinc-600/40 bg-white/[0.03]"
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
                    I agree to secure handling of my credit report (same terms as 850 Lab).
                  </span>
                </label>

                <div className="mt-4 sm:mt-5">
                  <UploadDropzoneCard
                    key={dropzoneResetKey}
                    disabled={!allowUpload || parseBusy}
                    onUploadPdfs={onUploadPdfs}
                  />
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>
      </StepMainColumn>
    </div>
  );
}
