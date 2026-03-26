import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AddressHelpDisclosure } from "@/components/AddressHelpDisclosure";
import { SignatureCard } from "@/components/SignatureCard";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { UploadRequirementCard } from "@/components/UploadRequirementCard";
import { VerificationActionSection } from "@/components/VerificationActionSection";
import {
  loadProofVerification,
  saveProofVerification,
  type ProofVerificationSnapshot,
} from "@/lib/proofVerificationStorage";
import { setWorkflowStep } from "@/lib/workflow";

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

function buildSnapshot(p: {
  idFileName: string | null;
  addressFileName: string | null;
  signatureMode: "draw" | "type";
  signatureTyped: string;
  signatureDrawDataUrl: string | null;
  signatureDrawComplete: boolean;
}): ProofVerificationSnapshot {
  const idComplete = !!p.idFileName;
  const addressComplete = !!p.addressFileName;
  const signatureComplete =
    p.signatureMode === "type"
      ? p.signatureTyped.trim().length >= 2
      : p.signatureDrawComplete && !!p.signatureDrawDataUrl;

  return {
    idFileName: p.idFileName,
    idComplete,
    addressFileName: p.addressFileName,
    addressComplete,
    signatureMode: p.signatureMode,
    signatureTyped: p.signatureTyped,
    signatureDrawDataUrl: p.signatureDrawDataUrl,
    signatureDrawComplete: p.signatureDrawComplete,
    signatureComplete,
    updatedAt: Date.now(),
  };
}

const addressExamples = (
  <p className="text-[13px] leading-relaxed sm:text-sm">
    <span className="text-lab-subtle">Examples: </span>
    utility bill · bank statement · phone bill · insurance document · government
    mail
  </p>
);

export function ProofVerificationPage() {
  const navigate = useNavigate();
  const [hydrated] = useState(() => loadProofVerification());

  const [idFileName, setIdFileName] = useState<string | null>(hydrated.idFileName);
  const [addressFileName, setAddressFileName] = useState<string | null>(
    hydrated.addressFileName,
  );
  const [signatureMode, setSignatureMode] = useState<"draw" | "type">(
    hydrated.signatureMode,
  );
  const [signatureTyped, setSignatureTyped] = useState(hydrated.signatureTyped);
  const [signatureDrawDataUrl, setSignatureDrawDataUrl] = useState<string | null>(
    hydrated.signatureDrawDataUrl,
  );
  const [signatureDrawComplete, setSignatureDrawComplete] = useState(
    hydrated.signatureDrawComplete,
  );
  const [savedHint, setSavedHint] = useState(false);

  const snapshot = useMemo(
    () =>
      buildSnapshot({
        idFileName,
        addressFileName,
        signatureMode,
        signatureTyped,
        signatureDrawDataUrl,
        signatureDrawComplete,
      }),
    [
      idFileName,
      addressFileName,
      signatureMode,
      signatureTyped,
      signatureDrawDataUrl,
      signatureDrawComplete,
    ],
  );

  const idComplete = !!idFileName;
  const addressComplete = !!addressFileName;
  const signatureComplete = snapshot.signatureComplete;
  const canSend = idComplete && addressComplete && signatureComplete;

  useEffect(() => {
    saveProofVerification(snapshot);
  }, [snapshot]);

  useEffect(() => {
    if (!savedHint) return;
    const t = window.setTimeout(() => setSavedHint(false), 4200);
    return () => window.clearTimeout(t);
  }, [savedHint]);

  const handleSend = () => {
    if (!canSend) return;
    setWorkflowStep("send");
    navigate("/send", { replace: true });
  };

  const handleSaveLater = () => {
    saveProofVerification(snapshot);
    setSavedHint(true);
  };

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
            We need to verify your identity so the credit bureaus can process your
            disputes.
          </motion.p>
          <motion.p
            variants={headerVariants}
            className="mx-auto mt-4 max-w-sm text-center text-sm font-medium text-lab-accent/95"
          >
            You’re almost done
          </motion.p>

          <motion.div
            variants={stackVariants}
            initial="hidden"
            animate="show"
            className="mt-10 flex flex-col gap-4 sm:mt-11 sm:gap-5"
          >
            <UploadRequirementCard
              title="Upload your ID"
              supportText="Use a driver’s license or government-issued photo ID"
              fileName={idFileName}
              complete={idComplete}
              onFileSelected={(file) => setIdFileName(file.name)}
              onClearFile={() => setIdFileName(null)}
            />

            <UploadRequirementCard
              title="Confirm your address"
              supportText="Upload a document that shows your name and current address"
              examples={addressExamples}
              footerSlot={<AddressHelpDisclosure />}
              fileName={addressFileName}
              complete={addressComplete}
              onFileSelected={(file) => setAddressFileName(file.name)}
              onClearFile={() => setAddressFileName(null)}
            />

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
              complete={signatureComplete}
            />
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
                Progress saved. Come back anytime—we’ll keep this ready for you.
              </motion.p>
            ) : null}
          </AnimatePresence>

          <VerificationActionSection
            canSend={canSend}
            onSend={handleSend}
            onSaveLater={handleSaveLater}
          />
        </motion.div>
      </main>
    </div>
  );
}
