import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BureauSendStatusRow } from "@/components/BureauSendStatusRow";
import { ProgramFlowBridge } from "@/components/ProgramFlowBridge";
import { MailTruthStatusCard } from "@/components/MailTruthStatusCard";
import { MailingCTASection } from "@/components/MailingCTASection";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
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
import {
  mailingTrackPrimaryButtonClass,
  orionNarrativeCoherent,
  orionStepHeroCopy,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import {
  easeStep,
  stepChildVariants as headerVariants,
  stepPageVariants as pageVariants,
} from "@/lib/motionStep";

function MailingProgressStrip({ mailingComplete }: { mailingComplete: boolean }) {
  const step2Done = mailingComplete;
  const step3Active = mailingComplete;

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
          <span className="ml-1.5">Proof completed</span>
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
          <span className="ml-1.5">Mailing confirmed</span>
        </li>
        <li
          className={
            step3Active
              ? "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text"
              : "progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted"
          }
        >
          <span className={step3Active ? "text-lab-accent" : "text-lab-subtle"}>3.</span>
          <span className="ml-1.5">Tracking begins next</span>
        </li>
      </ol>
    </motion.div>
  );
}

function MailingRoundContinuityModule({ mail }: { mail: MailContextPayload }) {
  const targets = mail.bureauTargets.length;
  const progressLine =
    targets > 0
      ? `Mailing progress: ${mail.mailedCount} of ${mail.mailGateExpected} bureau send${
          mail.mailGateExpected === 1 ? "" : "s"
        } recorded for this round.`
      : null;

  return (
    <div className="surface-round-continuity">
      <p className="text-xs font-medium uppercase tracking-[0.08em] text-lab-subtle">Your current round</p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        Your letters and proof from earlier steps are prepared for this round. This screen is where
        you confirm certified mail for each bureau — nothing was mailed before you act here. After
        sends are in motion, tracking is the next step.
      </p>
      {targets > 0 ? (
        <p className="mt-2 text-xs text-lab-subtle">
          This round includes {targets} mailing target{targets === 1 ? "" : "s"}.
          {mail.proofBothOnFile ? " Proof is on file." : ""}
        </p>
      ) : null}
      {progressLine ? <p className="mt-2 text-xs text-lab-subtle">{progressLine}</p> : null}
    </div>
  );
}

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
    orionViewModel,
    integrityHints,
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

  const mailingCompleteForStrip = useMemo(() => {
    if (!mail) return false;
    return mail.pendingSendCount === 0;
  }, [mail]);

  const MAIL_HERO_FALLBACK = {
    title: "Review and send the package for this round",
    subtitle:
      "Your letters and proof documents are now prepared. This is the step where you review the mailing details and confirm when you're ready to send.",
  } as const;

  const orionAuthority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const mailHero = useMemo(
    () => orionStepHeroCopy(orionAuthority, orionViewModel, MAIL_HERO_FALLBACK),
    [orionAuthority, orionViewModel],
  );

  const mailCoherent = useMemo(
    () => orionNarrativeCoherent(orionAuthority, orionViewModel),
    [orionAuthority, orionViewModel],
  );

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
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn className="relative z-10 mx-auto max-w-xl px-4 pb-24 pt-24 sm:px-6 sm:pb-28 sm:pt-28">
        {pageLoading ? (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2, ease: easeStep }}
            className="text-center text-sm text-lab-muted"
          >
            Loading mail status…
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

        {!pageLoading && mail ? (
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
              STEP 7 • CONFIRM YOUR MAILING
            </motion.p>
            <motion.h1
              variants={headerVariants}
              className="step-title"
            >
              {mailHero.title}
            </motion.h1>
            <motion.p
              variants={headerVariants}
              className="step-support"
            >
              {mailHero.subtitle}
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
                  <span>Your proof documents are already on file</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>This is the final confirmation step before mailing</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>Nothing is sent until you confirm on this page</span>
                </li>
              </ul>
            </motion.div>

            <MailingProgressStrip mailingComplete={mailingCompleteForStrip} />

            <motion.div variants={headerVariants} className="mx-auto mt-6 max-w-lg">
              <MailingRoundContinuityModule mail={mail} />
            </motion.div>

            <motion.div variants={headerVariants} className="mx-auto mt-5 max-w-lg">
              <ProgramFlowBridge>
                {mailCoherent ? (
                  <>
                    <span className="font-medium text-lab-text">Certified mail for this round</span> — confirm
                    each bureau below when you&apos;re ready; tracking follows in the same program.
                  </>
                ) : (
                  <>
                    <span className="font-medium text-lab-text">This is the first step where mail can go out:</span>{" "}
                    each bureau below is a separate confirm — you choose when. After that, tracking picks
                    up in the same program.
                  </>
                )}
              </ProgramFlowBridge>
            </motion.div>

            {!mailCoherent ? (
              <motion.p
                variants={headerVariants}
                className="mx-auto mt-5 max-w-lg text-center text-xs leading-relaxed text-lab-subtle sm:text-sm"
              >
                Review the details below, then confirm when ready. This is the control point before
                tracking begins — you are confirming mailing for this round, not an automatic send.
              </motion.p>
            ) : null}

            <motion.div
              variants={headerVariants}
              className="mx-auto mt-8 max-w-lg rounded-xl border border-white/[0.08] bg-lab-surface/50 px-4 py-4 sm:px-5 sm:py-5"
            >
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-lab-subtle">
                What&apos;s included in this mailing
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-relaxed text-lab-muted">
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>The dispute letters prepared for your confirmed round</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>The proof documents you added in the last step (already on file)</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-lab-accent/80" aria-hidden>
                    •
                  </span>
                  <span>The mailing package tied to this round, sent as USPS certified mail per bureau</span>
                </li>
              </ul>
            </motion.div>

            <motion.div variants={headerVariants}>
              <MailTruthStatusCard mail={mail} />
            </motion.div>

            {mail.onMailStep && !mail.hasMailingsEntitlement && mail.hasLetters && mail.proofBothOnFile ? (
              <motion.div
                variants={headerVariants}
                className="mx-auto mt-4 max-w-lg rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-50"
              >
                <p className="font-medium text-amber-100">This package is not ready to mail yet</p>
                <p className="mt-1.5 text-xs leading-relaxed text-amber-100/88">
                  You need at least one mailing credit on your account before a send can go out. Add
                  mailings from your account (same login), or check with your organization — then
                  refresh this page.
                </p>
                <Link
                  to="/"
                  className="mt-3 inline-block text-xs font-semibold text-amber-200 hover:text-amber-100"
                >
                  Go to home / account entry →
                </Link>
              </motion.div>
            ) : null}

            <motion.p
              variants={headerVariants}
              className="mx-auto mt-4 max-w-lg text-center text-xs text-lab-subtle"
            >
              Round progress: {mail.mailedCount} of {mail.mailGateExpected} bureau send
              {mail.mailGateExpected === 1 ? "" : "s"} recorded
              {mail.mailGateFailedSendCount > 0
                ? ` · ${mail.mailGateFailedSendCount} send attempt(s) need attention`
                : ""}
            </motion.p>

            <motion.section
              variants={headerVariants}
              className="mt-8 space-y-3 rounded-xl border border-white/[0.08] bg-lab-surface px-4 py-5 sm:px-5"
            >
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-lab-subtle">
                  Sending from
                </p>
                <p className="text-[13px] font-semibold text-lab-text">Your return address (USPS)</p>
                <p className="mt-1 text-xs text-lab-muted">
                  This address appears on your certified mail — double-check it before you confirm each
                  send.
                </p>
              </div>
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
              <p className="mt-4 text-center text-sm text-red-300/90">
                <span className="block text-lab-muted">This mailing was not completed yet.</span>
                <span className="mt-1 block">{sendError}</span>
              </p>
            ) : null}

            {lastSendWasTest === true ? (
              <p className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-center text-xs text-amber-200/95">
                Last send: <span className="font-semibold">Test mode</span> — no physical USPS letter.
                Your mailing credit was still applied when the processor accepted the request.
              </p>
            ) : lastSendWasTest === false ? (
              <p className="mt-4 text-center text-xs text-lab-muted">
                Last send: <span className="font-medium text-lab-text">Live mail</span> — the
                processor accepted your piece. Use the row below for USPS tracking; transit is not
                the same as bureau results.
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
                        className="w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white shadow-md shadow-black/35 disabled:pointer-events-none disabled:opacity-45"
                      >
                        {sendingBureau === t.bureau
                          ? "Confirming send…"
                          : `Confirm and send${mail.costEstimate?.totalDisplay ? ` (${mail.costEstimate.totalDisplay})` : ""}`}
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
              trackButtonClassName={mailingTrackPrimaryButtonClass(mailHero.ctaEmphasis)}
              headline={
                trackBlocked
                  ? "Confirm each bureau send below first"
                  : mailCoherent
                    ? "When sends are confirmed, continue to tracking"
                    : "Ready when mailing is complete"
              }
              supportText={
                trackBlocked
                  ? "Mailing has not been confirmed yet for every pending bureau. Use each row, then continue to tracking."
                  : mailCoherent
                    ? "Tracking opens in the same program once mailing is complete for this round."
                    : "Mailing is confirmed for this round. The next step is tracking — you’ll see status after sends are in motion."
              }
              helperText="Tracking begins after mailing is confirmed."
              trackLabel="Continue to Tracking"
            />
            {trackBlocked ? (
              <p className="mt-3 text-center text-xs text-lab-subtle">
                Complete each &quot;Confirm and send&quot; below when you&apos;re ready — one bureau at
                a time. Nothing goes out until you tap.
              </p>
            ) : null}
          </motion.div>
        ) : null}
      </StepMainColumn>
    </div>
  );
}
