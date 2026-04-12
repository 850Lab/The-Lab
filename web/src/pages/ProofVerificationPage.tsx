import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AddressHelpDisclosure } from "@/components/AddressHelpDisclosure";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { SignatureCard } from "@/components/SignatureCard";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { ProofMoreContextPanel } from "@/components/ProofMoreContextPanel";
import { ProofSupportScriptPanel } from "@/components/ProofSupportScriptPanel";
import { UploadRequirementCard } from "@/components/UploadRequirementCard";
import { VerificationActionSection } from "@/components/VerificationActionSection";
import type { ProofContextPayload } from "@/lib/proofTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";
import { dataUrlFromTypedSignature, dataUrlToPngBlob } from "@/lib/typedSignaturePng";
import {
  fetchProofContext,
  fetchWorkflowResume,
  postProofSignature,
  postProofUpload,
} from "@/lib/workflowApi";
import {
  customerPathFromEnvelope,
  isAuthoritativeStepBefore,
} from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  easeStep,
  stepChildVariants as headerVariants,
  stepPageVariants as pageVariants,
  stepStackVariants as stackVariants,
} from "@/lib/motionStep";
import {
  orionStepHeroCopy,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import { clearOptionalProofContextAugmentations } from "@/lib/proofContextAugmentationReset";
import {
  ORION_PROOF_STEP_COMPLETED,
  sendOrionProofSignal,
  type OrionProofSignalContext,
} from "@/lib/orionProofSignals";

const addressExamples = (
  <p className="text-[13px] leading-relaxed sm:text-sm">
    <span className="text-lab-subtle">Examples: </span>
    utility bill · bank statement · phone bill · insurance · government mail — anything that shows
    your name and current mailing address clearly
  </p>
);

function ProofProgressStrip({ proofPackageComplete }: { proofPackageComplete: boolean }) {
  const step2Done = proofPackageComplete;
  const step3Active = proofPackageComplete;

  return (
    <motion.div
      variants={headerVariants}
      className="surface-where-fits mx-auto mt-6 max-w-2xl"
    >
      <p className="text-center text-[10px] font-bold uppercase tracking-[0.16em] text-lab-subtle">
        What happens next
      </p>
      <ol className="mt-3 flex flex-col gap-2 text-sm sm:mt-4 sm:flex-row sm:justify-center sm:gap-3 sm:text-[13px]">
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted">
          <span className="font-semibold text-emerald-200/95">1.</span>
          <span className="ml-1.5">Letters prepared</span>
        </li>
        <li
          className={
            step2Done
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/[0.08] px-3 py-2.5 text-center text-lab-muted"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text"
          }
        >
          <span className={step2Done ? "font-semibold text-emerald-200/95" : "text-lab-accent"}>
            2.
          </span>
          <span className="ml-1.5">Proof completed</span>
        </li>
        <li
          className={
            step3Active
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted"
          }
        >
          <span className={step3Active ? "text-lab-accent" : "text-lab-subtle"}>3.</span>
          <span className="ml-1.5">Mailing next</span>
        </li>
      </ol>
    </motion.div>
  );
}

function ProofRoundContinuityModule({ proof }: { proof: ProofContextPayload }) {
  const done = [proof.hasGovernmentId, proof.hasAddressProof, proof.hasSignature].filter(Boolean)
    .length;

  return (
    <div className="surface-round-continuity">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-lab-subtle">
        Your current round
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        Your letters were prepared in the last step. This step adds the supporting documents and
        signature your mailing package needs before anything is sent. After this, you&apos;ll move to
        the final mailing screen — you still choose when mail goes out.
      </p>
      {done < 3 ? (
        <p className="mt-2 text-xs text-lab-subtle">
          You&apos;ve added {done} of 3 items for this step. You only need what&apos;s listed below.
        </p>
      ) : null}
    </div>
  );
}

function applyProofFromResponse(
  r: { workflow: WorkflowEnvelope; proof: ProofContextPayload },
  applyWorkflowEnvelope: (e: WorkflowEnvelope) => void,
  setProof: (p: ProofContextPayload) => void,
  setSupportingAiExplanation: (v: unknown) => void,
  setSupportingAiScript: (v: unknown) => void,
  setProofSignalMeta: (v: null) => void,
) {
  applyWorkflowEnvelope(r.workflow);
  setProof(r.proof);
  clearOptionalProofContextAugmentations(
    setSupportingAiExplanation,
    setSupportingAiScript,
    setProofSignalMeta,
  );
}

export function ProofVerificationPage() {
  const navigate = useNavigate();
  const {
    token,
    workflowId,
    authoritativeStepId,
    phase,
    envelope,
    applyWorkflowEnvelope,
    orionViewModel,
    integrityHints,
  } = useCustomerWorkflow();

  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [proof, setProof] = useState<ProofContextPayload | null>(null);
  /** Nullable ORION-grounded augmentation; cleared on upload/signature refresh responses. */
  const [supportingAiExplanation, setSupportingAiExplanation] = useState<unknown>(null);
  const [supportingAiScript, setSupportingAiScript] = useState<unknown>(null);
  const [proofSignalMeta, setProofSignalMeta] = useState<{
    scriptAugmentationStatus?: string;
    proofScriptRefinementStatus?: string;
  } | null>(null);

  const [replaceId, setReplaceId] = useState(false);
  const [replaceAddr, setReplaceAddr] = useState(false);
  const [replaceSig, setReplaceSig] = useState(false);

  const [idPendingFile, setIdPendingFile] = useState<File | null>(null);
  const [addrPendingFile, setAddrPendingFile] = useState<File | null>(null);

  const [idUploading, setIdUploading] = useState(false);
  const [addrUploading, setAddrUploading] = useState(false);
  const [sigUploading, setSigUploading] = useState(false);
  const [idUploadError, setIdUploadError] = useState<string | null>(null);
  const [addrUploadError, setAddrUploadError] = useState<string | null>(null);
  const [sigUploadError, setSigUploadError] = useState<string | null>(null);

  const [signatureMode, setSignatureMode] = useState<"draw" | "type">("draw");
  const [signatureTyped, setSignatureTyped] = useState("");
  const [signatureDrawDataUrl, setSignatureDrawDataUrl] = useState<string | null>(null);
  const [signatureDrawComplete, setSignatureDrawComplete] = useState(false);

  const [continueBusy, setContinueBusy] = useState(false);
  const [savedHint, setSavedHint] = useState(false);

  const PROOF_HERO_FALLBACK = {
    title: "Add the proof documents needed before mailing",
    subtitle:
      "This step helps complete the package for the round you already prepared. We'll use these documents to support your mailing package before anything is sent.",
  } as const;

  const orionAuthority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const proofHero = useMemo(
    () => orionStepHeroCopy(orionAuthority, orionViewModel, PROOF_HERO_FALLBACK),
    [orionAuthority, orionViewModel],
  );

  const proofScriptSignalContext = useMemo((): OrionProofSignalContext | null => {
    if (!token || !workflowId) return null;
    return {
      token,
      workflowId,
      contractCompleteness: orionViewModel.contractCompleteness,
      scriptAugmentationStatus: proofSignalMeta?.scriptAugmentationStatus,
      proofScriptRefinementStatus: proofSignalMeta?.proofScriptRefinementStatus,
    };
  }, [
    token,
    workflowId,
    orionViewModel.contractCompleteness,
    proofSignalMeta?.scriptAugmentationStatus,
    proofSignalMeta?.proofScriptRefinementStatus,
  ]);

  const proofStepCompleteSignalSent = useRef(false);
  useEffect(() => {
    proofStepCompleteSignalSent.current = false;
  }, [workflowId]);

  useEffect(() => {
    if (
      !token ||
      !workflowId ||
      !proof?.proofStepCompleted ||
      proofStepCompleteSignalSent.current
    ) {
      return;
    }
    proofStepCompleteSignalSent.current = true;
    const ctx: OrionProofSignalContext = {
      token,
      workflowId,
      contractCompleteness: orionViewModel.contractCompleteness,
      scriptAugmentationStatus: proofSignalMeta?.scriptAugmentationStatus,
      proofScriptRefinementStatus: proofSignalMeta?.proofScriptRefinementStatus,
    };
    sendOrionProofSignal(ctx, ORION_PROOF_STEP_COMPLETED);
  }, [
    token,
    workflowId,
    proof?.proofStepCompleted,
    orionViewModel.contractCompleteness,
    proofSignalMeta?.scriptAugmentationStatus,
    proofSignalMeta?.proofScriptRefinementStatus,
  ]);

  const proofContinueButtonClass =
    proofHero.ctaEmphasis === "dominant"
      ? "w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-black/40 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/45 disabled:cursor-not-allowed disabled:bg-lab-accent/35 disabled:text-white/70 disabled:shadow-none"
      : proofHero.ctaEmphasis === "standard"
        ? "w-full rounded-xl border border-lab-accent/45 bg-lab-accent/88 py-3.5 text-[15px] font-semibold text-white shadow-md shadow-black/35 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/38 disabled:cursor-not-allowed disabled:bg-lab-accent/35 disabled:text-white/70 disabled:shadow-none"
        : "w-full rounded-xl border border-white/15 bg-white/[0.06] py-3.5 text-[15px] font-semibold text-lab-text shadow-sm transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/22 disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none";

  const loadContext = useCallback(async () => {
    if (!token || !workflowId) {
      setProof(null);
      clearOptionalProofContextAugmentations(
        setSupportingAiExplanation,
        setSupportingAiScript,
        setProofSignalMeta,
      );
      setLoadError(null);
      setPageLoading(false);
      return;
    }
    setPageLoading(true);
    setLoadError(null);
    try {
      const data = await fetchProofContext(token, workflowId, {
        includeAiExplanation: true,
        includeAiScript: true,
      });
      applyWorkflowEnvelope(data.workflow);
      setProof(data.proof);
      setSupportingAiExplanation(data.aiExplanation ?? null);
      setSupportingAiScript(data.aiScript ?? null);
      setProofSignalMeta({
        scriptAugmentationStatus:
          typeof data.scriptAugmentationStatus === "string"
            ? data.scriptAugmentationStatus
            : undefined,
        proofScriptRefinementStatus:
          typeof data.proofScriptRefinementStatus === "string"
            ? data.proofScriptRefinementStatus
            : undefined,
      });
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setProof(null);
      clearOptionalProofContextAugmentations(
        setSupportingAiExplanation,
        setSupportingAiScript,
        setProofSignalMeta,
      );
    } finally {
      setPageLoading(false);
    }
  }, [token, workflowId, applyWorkflowEnvelope]);

  useEffect(() => {
    void loadContext();
  }, [loadContext]);

  useEffect(() => {
    if (pageLoading || loadError) return;
    if (!envelope) return;
    if (!authoritativeStepId) return;
    if (isAuthoritativeStepBefore(authoritativeStepId, "proof_attachment")) {
      navigate(customerPathFromEnvelope(envelope), { replace: true });
    }
  }, [pageLoading, loadError, envelope, authoritativeStepId, navigate]);

  useEffect(() => {
    if (!savedHint) return;
    const t = window.setTimeout(() => setSavedHint(false), 4200);
    return () => window.clearTimeout(t);
  }, [savedHint]);

  const handleUploadId = async () => {
    if (!proof?.onProofAttachmentStep) return;
    if (!token || !workflowId || !idPendingFile) return;
    setIdUploading(true);
    setIdUploadError(null);
    try {
      const r = await postProofUpload(token, workflowId, "government_id", idPendingFile);
      applyProofFromResponse(
        r,
        applyWorkflowEnvelope,
        setProof,
        setSupportingAiExplanation,
        setSupportingAiScript,
        setProofSignalMeta,
      );
      setIdPendingFile(null);
      setReplaceId(false);
    } catch (e) {
      setIdUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setIdUploading(false);
    }
  };

  const handleUploadAddr = async () => {
    if (!proof?.onProofAttachmentStep) return;
    if (!token || !workflowId || !addrPendingFile) return;
    setAddrUploading(true);
    setAddrUploadError(null);
    try {
      const r = await postProofUpload(token, workflowId, "address_proof", addrPendingFile);
      applyProofFromResponse(
        r,
        applyWorkflowEnvelope,
        setProof,
        setSupportingAiExplanation,
        setSupportingAiScript,
        setProofSignalMeta,
      );
      setAddrPendingFile(null);
      setReplaceAddr(false);
    } catch (e) {
      setAddrUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setAddrUploading(false);
    }
  };

  const signatureReadyLocal =
    signatureMode === "type"
      ? signatureTyped.trim().length >= 2
      : signatureDrawComplete && !!signatureDrawDataUrl;

  const handleSaveSignature = async () => {
    if (!proof?.onProofAttachmentStep) return;
    if (!token || !workflowId || !signatureReadyLocal) return;
    setSigUploading(true);
    setSigUploadError(null);
    try {
      let dataUrl: string | null = null;
      if (signatureMode === "draw") {
        dataUrl = signatureDrawDataUrl;
      } else {
        dataUrl = dataUrlFromTypedSignature(signatureTyped);
      }
      if (!dataUrl) {
        setSigUploadError(
          "We couldn’t create a signature image from that. Try again, or switch between draw and type.",
        );
        return;
      }
      const blob = await dataUrlToPngBlob(dataUrl);
      const r = await postProofSignature(token, workflowId, blob);
      applyProofFromResponse(
        r,
        applyWorkflowEnvelope,
        setProof,
        setSupportingAiExplanation,
        setSupportingAiScript,
        setProofSignalMeta,
      );
      setReplaceSig(false);
    } catch (e) {
      setSigUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setSigUploading(false);
    }
  };

  const handleContinue = async () => {
    if (!token || !workflowId) return;
    setContinueBusy(true);
    setLoadError(null);
    try {
      const env = await fetchWorkflowResume(token, workflowId);
      applyWorkflowEnvelope(env);
      navigate(customerPathFromEnvelope(env), { replace: true });
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setContinueBusy(false);
    }
  };

  const handleSaveLater = () => {
    setSavedHint(true);
  };

  const idCompleteOnServer = !!proof?.hasGovernmentId && !replaceId && !idPendingFile;
  const addrCompleteOnServer = !!proof?.hasAddressProof && !replaceAddr && !addrPendingFile;
  const sigCompleteOnServer = !!proof?.hasSignature && !replaceSig;

  const idDisplayName =
    idPendingFile?.name ??
    (!replaceId ? (proof?.governmentId?.fileName ?? null) : null);
  const addrDisplayName =
    addrPendingFile?.name ??
    (!replaceAddr ? (proof?.addressProof?.fileName ?? null) : null);

  const canContinue =
    phase === "done" ||
    authoritativeStepId !== "proof_attachment" ||
    !!proof?.proofStepCompleted;

  const stepsDone =
    (proof?.hasGovernmentId ? 1 : 0) + (proof?.hasAddressProof ? 1 : 0);

  const proofPackageComplete =
    !!proof?.hasGovernmentId && !!proof?.hasAddressProof && !!proof?.hasSignature;

  const allowProofEdits = !!proof?.onProofAttachmentStep;

  return (
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn className="relative z-10 mx-auto max-w-xl px-4 pb-28 pt-24 sm:px-6 sm:pb-32 sm:pt-28">
        {pageLoading ? (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="text-center text-sm text-lab-muted"
          >
            Loading verification status…
          </motion.p>
        ) : null}
        {loadError ? (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="mt-4 text-center text-sm text-red-300/90"
          >
            {loadError}
          </motion.p>
        ) : null}

        {!pageLoading && proof ? (
          <motion.div
            variants={pageVariants}
            initial="hidden"
            animate="show"
            className="pb-4"
          >
            <motion.p
              variants={headerVariants}
              className="step-eyebrow"
            >
              STEP 6 • VERIFY YOUR MAILING PACKAGE
            </motion.p>
            <motion.h1
              variants={headerVariants}
              className="step-title"
            >
              {proofHero.title}
            </motion.h1>
            <motion.p
              variants={headerVariants}
              className="step-support"
            >
              {proofHero.subtitle}
            </motion.p>
            <motion.div
              variants={headerVariants}
              className="surface-emerald-reassure mx-auto mt-6 max-w-lg"
            >
              <ul className="space-y-2 text-left text-sm leading-relaxed text-emerald-50/95 sm:text-[15px]">
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>This step verifies the mailing package for your current round</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>Your letters are already prepared from the previous step</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>Nothing is mailed from this page</span>
                </li>
              </ul>
            </motion.div>

            <ProofMoreContextPanel aiExplanation={supportingAiExplanation} />

            <ProofSupportScriptPanel
              aiScript={supportingAiScript}
              signalContext={proofScriptSignalContext}
            />

            <ProofProgressStrip proofPackageComplete={proofPackageComplete} />

            <motion.div variants={headerVariants} className="mx-auto mt-6 max-w-lg">
              <ProofRoundContinuityModule proof={proof} />
            </motion.div>

            <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-lg">
              <ProgramFlowBridge>
                <span className="font-medium text-lab-text">Same program, next preparation step:</span>{" "}
                you&apos;re adding what the mail partner needs to attach your identity to this round.
                Nothing is sent from here — the mailing screen is next, and you still confirm there.
              </ProgramFlowBridge>
            </motion.div>

            <motion.div
              variants={headerVariants}
              className="mx-auto mt-8 max-w-lg rounded-xl border border-white/[0.08] bg-lab-surface/50 px-4 py-4 sm:px-5 sm:py-5"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-lab-subtle">
                Why we ask for this
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-relaxed text-lab-muted">
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>It helps complete the mailing package for your dispute round</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>
                    It matches your identity and address to the documents that will be mailed on your
                    behalf
                  </span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>It&apos;s a normal part of preparing certified mail — not a surprise extra step</span>
                </li>
              </ul>
            </motion.div>

            <motion.p
              variants={headerVariants}
              className="mx-auto mt-5 max-w-lg text-center text-xs leading-relaxed text-lab-subtle sm:text-sm"
            >
              If something is missing or unclear, we&apos;ll let you know before you continue. You
              only need the items listed below for this step — this is just to complete your package
              before mailing.
            </motion.p>

            <motion.p
              variants={headerVariants}
              className="mx-auto mt-4 max-w-lg text-center text-sm text-lab-muted"
            >
              {proof.proofStepCompleted
                ? "Verification for this step is complete."
                : `Documents on file: ${stepsDone} of 2.`}
              {!proof.proofStepCompleted ? (
                <>
                  {" "}
                  {proof.hasSignature ? "Signature on file." : "Signature still needed."}
                </>
              ) : null}
            </motion.p>

            <motion.div
              variants={stackVariants}
              initial="hidden"
              animate="show"
              className="mt-10 flex flex-col gap-4 sm:mt-11 sm:gap-5"
            >
              <div
                className={
                  allowProofEdits ? undefined : "pointer-events-none select-none opacity-[0.88]"
                }
              >
                <UploadRequirementCard
                  title="Government-issued ID"
                  supportText="Driver’s license, state ID, passport, or other government photo ID with your name and photo visible."
                  formatHint="Clear photos or PDFs are usually fine."
                  fileName={idDisplayName}
                  complete={idCompleteOnServer}
                  onFileSelected={(f) => {
                    if (!allowProofEdits) return;
                    setIdPendingFile(f);
                    setIdUploadError(null);
                  }}
                  onClearFile={() => {
                    if (!allowProofEdits) return;
                    setIdPendingFile(null);
                  }}
                  onCommit={
                    allowProofEdits && idPendingFile ? handleUploadId : undefined
                  }
                  commitBusy={idUploading}
                  commitLabel="Save this ID"
                />
                {idCompleteOnServer && allowProofEdits ? (
                  <button
                    type="button"
                    onClick={() => {
                      setReplaceId(true);
                      setIdPendingFile(null);
                    }}
                    className="mt-2 w-full rounded-lg border border-white/[0.1] py-2.5 text-sm text-lab-muted transition-colors hover:border-white/[0.16] hover:text-lab-text"
                  >
                    Replace ID
                  </button>
                ) : null}
                {idUploadError ? (
                  <p className="mt-2 text-center text-sm text-red-300/90">
                    <span className="block text-lab-muted">Your upload was not completed yet.</span>
                    <span className="mt-1 block">{idUploadError}</span>
                  </p>
                ) : null}
              </div>

              <div
                className={
                  allowProofEdits ? undefined : "pointer-events-none select-none opacity-[0.88]"
                }
              >
                <UploadRequirementCard
                  title="Proof of address"
                  supportText="A document that shows your name and current mailing address (same address you use for this dispute)."
                  formatHint="Clear photos or PDFs are usually fine."
                  examples={addressExamples}
                  footerSlot={<AddressHelpDisclosure />}
                  fileName={addrDisplayName}
                  complete={addrCompleteOnServer}
                  onFileSelected={(f) => {
                    if (!allowProofEdits) return;
                    setAddrPendingFile(f);
                    setAddrUploadError(null);
                  }}
                  onClearFile={() => {
                    if (!allowProofEdits) return;
                    setAddrPendingFile(null);
                  }}
                  onCommit={
                    allowProofEdits && addrPendingFile ? handleUploadAddr : undefined
                  }
                  commitBusy={addrUploading}
                  commitLabel="Save this document"
                />
                {addrCompleteOnServer && allowProofEdits ? (
                  <button
                    type="button"
                    onClick={() => {
                      setReplaceAddr(true);
                      setAddrPendingFile(null);
                    }}
                    className="mt-2 w-full rounded-lg border border-white/[0.1] py-2.5 text-sm text-lab-muted transition-colors hover:border-white/[0.16] hover:text-lab-text"
                  >
                    Replace address proof
                  </button>
                ) : null}
                {addrUploadError ? (
                  <p className="mt-2 text-center text-sm text-red-300/90">
                    <span className="block text-lab-muted">Your upload was not completed yet.</span>
                    <span className="mt-1 block">{addrUploadError}</span>
                  </p>
                ) : null}
              </div>

              {sigCompleteOnServer ? (
                <motion.section
                  variants={{
                    hidden: { opacity: 0, y: 16 },
                    show: {
                      opacity: 1,
                      y: 0,
                      transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
                    },
                  }}
                  className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 shadow-lg shadow-black/15 sm:px-6 sm:py-6"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
                        Signature confirmation
                      </h3>
                      <p className="mt-1.5 text-sm text-lab-muted">
                        On file for this round — part of your mailing package. Nothing is sent from
                        this page.
                      </p>
                    </div>
                    <span className="flex h-8 shrink-0 items-center rounded-full bg-emerald-500/12 px-2.5 text-xs font-medium text-emerald-300/95">
                      Added
                    </span>
                  </div>
                  {allowProofEdits ? (
                    <button
                      type="button"
                      onClick={() => {
                        setReplaceSig(true);
                        setSignatureDrawComplete(false);
                        setSignatureDrawDataUrl(null);
                        setSignatureTyped("");
                      }}
                      className="mt-4 w-full rounded-lg border border-white/[0.12] py-2.5 text-sm font-medium text-lab-text transition-colors hover:bg-white/[0.04]"
                    >
                      Replace signature
                    </button>
                  ) : null}
                </motion.section>
              ) : !allowProofEdits ? (
                <p className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 text-center text-sm text-lab-muted">
                  Signature can be added when this verification step is active. If this step is
                  already complete for your program, use continue below.
                </p>
              ) : (
                <>
                  <SignatureCard
                    title="Signature confirmation"
                    description="This signature is part of completing the mailing package tied to your current round."
                    mode={signatureMode}
                    onModeChange={setSignatureMode}
                    typedValue={signatureTyped}
                    onTypedChange={setSignatureTyped}
                    drawDataUrl={signatureDrawDataUrl}
                    drawComplete={signatureDrawComplete}
                    onDrawConfirm={(url) => {
                      setSignatureDrawDataUrl(url);
                      setSignatureDrawComplete(true);
                    }}
                    onDrawClear={() => {
                      setSignatureDrawDataUrl(null);
                      setSignatureDrawComplete(false);
                    }}
                    complete={false}
                  />
                  <button
                    type="button"
                    onClick={() => void handleSaveSignature()}
                    disabled={!signatureReadyLocal || sigUploading}
                    className="w-full rounded-xl bg-lab-accent/20 py-3 text-[15px] font-semibold text-lab-accent transition-colors hover:bg-lab-accent/28 disabled:pointer-events-none disabled:opacity-45"
                  >
                    {sigUploading ? "Saving signature…" : "Save signature"}
                  </button>
                  {sigUploadError ? (
                    <p className="text-center text-sm text-red-300/90">
                      <span className="block text-lab-muted">This signature still needs to be saved.</span>
                      <span className="mt-1 block">{sigUploadError}</span>
                    </p>
                  ) : null}
                </>
              )}
            </motion.div>

            <AnimatePresence>
              {savedHint ? (
                <motion.p
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.3 }}
                  className="mt-6 text-center text-sm text-emerald-300/90"
                >
                  Anything you&apos;ve saved here stays on your account. Continue whenever you&apos;re
                  ready — mailing is still on the next step.
                </motion.p>
              ) : null}
            </AnimatePresence>

            <VerificationActionSection
              canSend={canContinue}
              onSend={handleContinue}
              onSaveLater={handleSaveLater}
              sendBusy={continueBusy}
              sendButtonClassName={proofContinueButtonClass}
            />
          </motion.div>
        ) : null}
      </StepMainColumn>
    </div>
  );
}
