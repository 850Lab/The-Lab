import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BureauSendStatusRow } from "@/components/BureauSendStatusRow";
import { MailTruthStatusCard } from "@/components/MailTruthStatusCard";
import { MailingCTASection } from "@/components/MailingCTASection";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import type { MailContextPayload } from "@/lib/mailTypes";
import type { WorkflowEnvelope } from "@/lib/workflowTypes";
import {
  fetchMailContext,
  fetchWorkflowResume,
  postMailSendBureau,
} from "@/lib/workflowApi";
import {
  customerPathFromEnvelope,
  isAuthoritativeStepBefore,
} from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const headerVariants = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.42, ease: [0.22, 1, 0.36, 1] },
  },
};

function applyMailResponse(
  r: { workflow: WorkflowEnvelope; mail: MailContextPayload },
  applyWorkflowEnvelope: (e: WorkflowEnvelope) => void,
  setMail: (m: MailContextPayload) => void,
) {
  applyWorkflowEnvelope(r.workflow);
  setMail(r.mail);
}

export function MailingPage() {
  const navigate = useNavigate();
  const {
    token,
    workflowId,
    authoritativeStepId,
    envelope,
    applyWorkflowEnvelope,
  } = useCustomerWorkflow();

  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mail, setMail] = useState<MailContextPayload | null>(null);

  const [name, setName] = useState("");
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zip, setZip] = useState("");
  const [returnReceipt, setReturnReceipt] = useState(true);

  const [sendingBureau, setSendingBureau] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [trackBusy, setTrackBusy] = useState(false);
  const [lastSendWasTest, setLastSendWasTest] = useState<boolean | null>(null);

  const loadContext = useCallback(async () => {
    if (!token || !workflowId) {
      setMail(null);
      setLoadError(null);
      setPageLoading(false);
      return;
    }
    setPageLoading(true);
    setLoadError(null);
    try {
      const data = await fetchMailContext(token, workflowId);
      applyMailResponse(data, applyWorkflowEnvelope, setMail);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setMail(null);
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
    if (isAuthoritativeStepBefore(authoritativeStepId, "mail")) {
      navigate(customerPathFromEnvelope(envelope), { replace: true });
    }
  }, [pageLoading, loadError, envelope, authoritativeStepId, navigate]);

  const addressValid = useMemo(() => {
    const st = state.trim().toUpperCase();
    return (
      name.trim().length >= 1 &&
      line1.trim().length >= 1 &&
      city.trim().length >= 1 &&
      st.length === 2 &&
      zip.trim().length >= 3
    );
  }, [name, line1, city, state, zip]);

  const canAttemptSend = useMemo(() => {
    if (!mail) return false;
    return (
      mail.onMailStep &&
      !mail.mailStatus.isBlocked &&
      mail.hasLetters &&
      mail.proofBothOnFile &&
      mail.lobConfigured &&
      mail.hasMailingsEntitlement &&
      addressValid
    );
  }, [mail, addressValid]);

  const trackBlocked = useMemo(() => {
    if (!mail) return true;
    return mail.onMailStep && mail.pendingSendCount > 0;
  }, [mail]);

  const handleSendBureau = async (bureau: string) => {
    if (!token || !workflowId || !canAttemptSend) return;
    setSendingBureau(bureau);
    setSendError(null);
    try {
      const st = state.trim().toUpperCase().slice(0, 2);
      const r = await postMailSendBureau(token, workflowId, {
        bureau,
        return_receipt: returnReceipt,
        from_address: {
          name: name.trim(),
          address_line1: line1.trim(),
          address_line2: line2.trim(),
          address_city: city.trim(),
          address_state: st,
          address_zip: zip.trim(),
        },
      });
      setLastSendWasTest(Boolean(r.lob?.isTest));
      applyMailResponse(r, applyWorkflowEnvelope, setMail);
    } catch (e) {
      setSendError(e instanceof Error ? e.message : String(e));
      await loadContext();
    } finally {
      setSendingBureau(null);
    }
  };

  const handleTrack = async () => {
    if (!token || !workflowId || trackBlocked) return;
    setTrackBusy(true);
    setLoadError(null);
    try {
      const env = await fetchWorkflowResume(token, workflowId);
      applyWorkflowEnvelope(env);
      navigate(customerPathFromEnvelope(env), { replace: true });
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
    } finally {
      setTrackBusy(false);
    }
  };

  const stateOptions = mail?.usStateOptions ?? [];

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

      <main className="relative z-10 mx-auto max-w-md px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        {pageLoading ? (
          <p className="text-center text-sm text-lab-muted">Loading mail status…</p>
        ) : null}
        {loadError ? (
          <p className="mt-4 text-center text-sm text-red-300/90">{loadError}</p>
        ) : null}

        {!pageLoading && mail ? (
          <motion.div initial="hidden" animate="show" className="pb-4">
            <motion.p
              variants={headerVariants}
              className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
            >
              Mail
            </motion.p>
            <motion.h1
              variants={headerVariants}
              className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
            >
              Send certified mail
            </motion.h1>
            <motion.p
              variants={headerVariants}
              className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
            >
              Generating letters does not mail them. Below is the exact status from the server for
              this workflow — including test vs live and what is blocking send.
            </motion.p>

            <motion.div variants={headerVariants}>
              <MailTruthStatusCard mail={mail} />
            </motion.div>

            <motion.p
              variants={headerVariants}
              className="mx-auto mt-4 max-w-sm text-center text-xs text-lab-subtle"
            >
              Progress: {mail.mailedCount} of {mail.mailGateExpected} bureau send
              {mail.mailGateExpected === 1 ? "" : "s"} recorded for this workflow
              {mail.mailGateFailedSendCount > 0
                ? ` · ${mail.mailGateFailedSendCount} failed attempt(s) logged`
                : ""}
            </motion.p>

            <motion.section
              variants={headerVariants}
              className="mt-8 space-y-3 rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-5 sm:px-5"
            >
              <p className="text-[13px] font-semibold text-lab-text">Your return address</p>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Full name"
                autoComplete="name"
                disabled={!mail.onMailStep}
                className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle disabled:opacity-50"
              />
              <input
                value={line1}
                onChange={(e) => setLine1(e.target.value)}
                placeholder="Street address"
                autoComplete="address-line1"
                disabled={!mail.onMailStep}
                className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle disabled:opacity-50"
              />
              <input
                value={line2}
                onChange={(e) => setLine2(e.target.value)}
                placeholder="Apt / suite (optional)"
                autoComplete="address-line2"
                disabled={!mail.onMailStep}
                className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle disabled:opacity-50"
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  placeholder="City"
                  autoComplete="address-level2"
                  disabled={!mail.onMailStep}
                  className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle disabled:opacity-50"
                />
                <select
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  disabled={!mail.onMailStep || !stateOptions.length}
                  className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text disabled:opacity-50"
                >
                  <option value="">State</option>
                  {stateOptions.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>
              <input
                value={zip}
                onChange={(e) => setZip(e.target.value)}
                placeholder="ZIP"
                autoComplete="postal-code"
                disabled={!mail.onMailStep}
                className="w-full rounded-lg border border-white/[0.1] bg-lab-elevated/80 px-3 py-2.5 text-sm text-lab-text placeholder:text-lab-subtle disabled:opacity-50"
              />
              <label className="flex items-center gap-2 text-sm text-lab-muted">
                <input
                  type="checkbox"
                  checked={returnReceipt}
                  onChange={(e) => setReturnReceipt(e.target.checked)}
                  disabled={!mail.onMailStep}
                  className="rounded border-white/20 bg-lab-elevated"
                />
                Include return receipt (USPS)
              </label>
              {mail.costEstimate?.totalDisplay ? (
                <p className="text-xs text-lab-subtle">
                  Est. per letter {mail.costEstimate.totalDisplay}
                  {mail.costEstimate.breakdown ? ` (${mail.costEstimate.breakdown})` : ""}
                </p>
              ) : null}
            </motion.section>

            {sendError ? (
              <p className="mt-4 text-center text-sm text-red-300/90">{sendError}</p>
            ) : null}

            {lastSendWasTest === true ? (
              <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-center text-xs text-amber-200/95">
                Last action: Lob accepted a <span className="font-semibold">test</span> request. No
                physical USPS letter was sent. A mailing credit was recorded after the processor
                accepted the request.
              </p>
            ) : lastSendWasTest === false ? (
              <p className="mt-4 text-center text-xs text-lab-muted">
                Last action: <span className="font-medium text-lab-text">Live</span> submission — the
                mail processor accepted the piece. Use the bureau row for USPS tracking; transit
                updates are not proof of delivery.
              </p>
            ) : null}

            <motion.div variants={headerVariants} className="mt-8 flex flex-col gap-3 sm:mt-9">
              {mail.bureauTargets.map((t) => (
                <BureauSendStatusRow
                  key={`${t.bureau}-${t.reportId}`}
                  bureauDisplay={t.bureauDisplay}
                  mailRowState={t.mailRowState}
                  isTestSend={t.isTestSend}
                  lobId={t.lobId}
                  lobErrorMessageSafe={t.lobErrorMessageSafe}
                  trackingNumber={t.trackingNumber}
                  trackingUrl={t.trackingUrl}
                  expectedDelivery={t.expectedDelivery}
                  actionSlot={
                    mail.onMailStep && t.sendStatus === "pending" ? (
                      <button
                        type="button"
                        disabled={!canAttemptSend || sendingBureau !== null}
                        onClick={() => void handleSendBureau(t.bureau)}
                        className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white shadow-md shadow-lab-accent/20 disabled:pointer-events-none disabled:opacity-45"
                      >
                        {sendingBureau === t.bureau
                          ? "Sending…"
                          : `Send certified to ${t.bureauDisplay}${
                              mail.costEstimate?.totalDisplay
                                ? ` (${mail.costEstimate.totalDisplay})`
                                : ""
                            }`}
                      </button>
                    ) : null
                  }
                />
              ))}
            </motion.div>

            <MailingCTASection
              onTrack={handleTrack}
              disabled={trackBlocked}
              busy={trackBusy}
            />
            {trackBlocked ? (
              <p className="mt-3 text-center text-xs text-lab-subtle">
                Send each pending bureau letter to continue to tracking.
              </p>
            ) : null}
          </motion.div>
        ) : null}
      </main>
    </div>
  );
}
