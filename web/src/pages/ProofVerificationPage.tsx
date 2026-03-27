import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AddressHelpDisclosure } from "@/components/AddressHelpDisclosure";
import { SignatureCard } from "@/components/SignatureCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
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

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.09, delayChildren: 0.04 },
  },
};

const headerVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

const stackVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.08 },
  },
};

const addressExamples = (
  <p className="text-[13px] leading-relaxed sm:text-sm">
    <span className="text-lab-subtle">Examples: </span>
    utility bill · bank statement · phone bill · insurance document · government
    mail
  </p>
);

function applyProofFromResponse(
  r: { workflow: WorkflowEnvelope; proof: ProofContextPayload },
  applyWorkflowEnvelope: (e: WorkflowEnvelope) => void,
  setProof: (p: ProofContextPayload) => void,
) {
  applyWorkflowEnvelope(r.workflow);
  setProof(r.proof);
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
  } = useCustomerWorkflow();

  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [proof, setProof] = useState<ProofContextPayload | null>(null);

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

  const loadContext = useCallback(async () => {
    if (!token || !workflowId) {
      setProof(null);
      setLoadError(null);
      setPageLoading(false);
      return;
    }
    setPageLoading(true);
    setLoadError(null);
    try {
      const data = await fetchProofContext(token, workflowId);
      applyProofFromResponse(data, applyWorkflowEnvelope, setProof);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setProof(null);
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
      applyProofFromResponse(r, applyWorkflowEnvelope, setProof);
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
      applyProofFromResponse(r, applyWorkflowEnvelope, setProof);
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
        setSigUploadError("Could not build a signature image. Check the name you typed.");
        return;
      }
      const blob = await dataUrlToPngBlob(dataUrl);
      const r = await postProofSignature(token, workflowId, blob);
      applyProofFromResponse(r, applyWorkflowEnvelope, setProof);
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

  const allowProofEdits = !!proof?.onProofAttachmentStep;

  return (
    <div className="relative min-h-full bg-lab-bg">
      <div
        className="pointer-events-none absolute left-1/2 top-[36%] z-0 h-[min(72vw,480px)] w-[min(72vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.09] blur-[110px]"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-[40%] z-0 h-[min(48vw,320px)] w-[min(48vw,320px)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-lab-accent/[0.04] blur-[90px]"
        aria-hidden
      />

      <TopBarMinimal />

      <main className="relative z-10 mx-auto max-w-md px-4 pb-28 pt-24 sm:px-6 sm:pb-32 sm:pt-28">
        {pageLoading ? (
          <p className="text-center text-sm text-lab-muted">Loading verification status…</p>
        ) : null}
        {loadError ? (
          <p className="mt-4 text-center text-sm text-red-300/90">{loadError}</p>
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
              className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
            >
              Verify
            </motion.p>
            <motion.h1
              variants={headerVariants}
              className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
            >
              One quick step before we send everything
            </motion.h1>
            <motion.p
              variants={headerVariants}
              className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
            >
              Government ID, proof of address, and your signature are stored on your account and are
              required before the send step — the mail processor will not accept certified sends
              without them (same rules as the main app).
            </motion.p>

            <motion.p
              variants={headerVariants}
              className="mx-auto mt-4 max-w-sm text-center text-sm text-lab-muted"
            >
              {proof.proofStepCompleted
                ? "All set — proof step is complete."
                : `${stepsDone} of 2 documents on file`}
              {proof.hasSignature ? " · Signature on file" : " · Signature missing"}
            </motion.p>

            {proof.onProofAttachmentStep && !proof.proofStepCompleted ? (
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-2 max-w-sm text-center text-xs text-lab-subtle"
              >
                Workflow step: proof attachment (in progress).
              </motion.p>
            ) : null}

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
                  title="Upload your ID"
                  supportText="Use a driver’s license or government-issued photo ID"
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
                  commitLabel="Save ID to account"
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
                  <p className="mt-2 text-center text-sm text-red-300/90">{idUploadError}</p>
                ) : null}
              </div>

              <div
                className={
                  allowProofEdits ? undefined : "pointer-events-none select-none opacity-[0.88]"
                }
              >
                <UploadRequirementCard
                  title="Confirm your address"
                  supportText="Upload a document that shows your name and current address"
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
                  commitLabel="Save address proof to account"
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
                  <p className="mt-2 text-center text-sm text-red-300/90">{addrUploadError}</p>
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
                        Signature
                      </h3>
                      <p className="mt-1.5 text-sm text-lab-muted">
                        On file — we’ll place this on your dispute letters.
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
                  Add or replace your signature when the proof step is active. Continue below if this
                  step is already complete.
                </p>
              ) : (
                <>
                  <SignatureCard
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
                    {sigUploading ? "Saving signature…" : "Save signature to account"}
                  </button>
                  {sigUploadError ? (
                    <p className="text-center text-sm text-red-300/90">{sigUploadError}</p>
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
                  Anything you’ve uploaded is already saved to your account. Continue whenever
                  you’re ready.
                </motion.p>
              ) : null}
            </AnimatePresence>

            <VerificationActionSection
              canSend={canContinue}
              onSend={handleContinue}
              onSaveLater={handleSaveLater}
              sendBusy={continueBusy}
            />
          </motion.div>
        ) : null}
      </main>
    </div>
  );
}
