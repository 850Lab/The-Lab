import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PaymentShell } from "@/components/PaymentShell";
import { PreparedItemsSummary, type PreparedCategory } from "@/components/PreparedItemsSummary";
import { StepPageAmbientBackground } from "@/components/StepPageAmbientBackground";
import { StepMainColumn } from "@/components/StepMainColumn";
import { TopBarMinimal } from "@/components/TopBarMinimal";
import { ValueRecapList } from "@/components/ValueRecapList";
import type { PaymentContextPayload } from "@/lib/paymentTypes";
import {
  fetchPaymentContext,
  postPaymentCheckout,
  postPaymentContinueWithCredits,
  postPaymentReconcile,
} from "@/lib/workflowApi";
import {
  NEXT_STEP_AFTER_PAYMENT_LINE,
  PAYMENT_WHAT_HAPPENS_NEXT_LINES,
} from "@/lib/flowMicrocopy";
import {
  orionStepHeroCopy,
  paymentRecommendedCheckoutButtonClass,
  resolveOrionAuthority,
} from "@/lib/orion/orionAuthority";
import { customerPathFromEnvelope } from "@/lib/workflowStepRoutes";
import { stepMainColumnTopClass } from "@/lib/stepPageLayout";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
import {
  stepChildVariants as headerVariants,
  stepPageVariants as pageVariants,
} from "@/lib/motionStep";

function formatUsd(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

function buildCategories(p: PaymentContextPayload): PreparedCategory[] {
  const out: PreparedCategory[] = [
    { label: "Bureau letter targets (this round)", count: p.neededLetters },
  ];
  if (p.selectedDisputeItemCount != null) {
    out.unshift({
      label: "Items confirmed in Strategy",
      count: p.selectedDisputeItemCount,
    });
  }
  return out;
}

function PaymentNextStepsStrip() {
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
          <span className="ml-1.5">Round confirmed</span>
        </li>
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-zinc-500/35 bg-zinc-500/[0.1] px-3 py-2.5 text-center font-semibold text-lab-text">
          <span className="text-lab-accent">2.</span>
          <span className="ml-1.5">This step</span>
        </li>
        <li className="progress-strip-pill flex flex-1 items-center justify-center rounded-lg border border-white/[0.08] bg-black/25 px-3 py-2.5 text-center text-lab-muted">
          <span className="text-lab-subtle">3.</span>
          <span className="ml-1.5">Letters &amp; next prep</span>
        </li>
      </ol>
    </motion.div>
  );
}

export function PaymentPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    token,
    workflowId,
    authoritativeStepId,
    canonicalCustomerPath,
    applyWorkflowEnvelope,
    orionViewModel,
    integrityHints,
  } = useCustomerWorkflow();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pay, setPay] = useState<PaymentContextPayload | null>(null);
  const [checkoutLoadingId, setCheckoutLoadingId] = useState<string | null>(null);
  const [creditsLoading, setCreditsLoading] = useState(false);
  const [reconcileError, setReconcileError] = useState<string | null>(null);
  const [reconcileBusy, setReconcileBusy] = useState(false);
  const [paymentStepPending, setPaymentStepPending] = useState(false);
  const reconciledSidRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    if (!token || !workflowId) {
      setPay(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const r = await fetchPaymentContext(token, workflowId);
      setPay(r.payment);
      applyWorkflowEnvelope(r.workflow);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPay(null);
    } finally {
      setLoading(false);
    }
  }, [token, workflowId, applyWorkflowEnvelope]);

  useEffect(() => {
    void load();
  }, [load]);

  const PAYMENT_HERO_FALLBACK = {
    title: "We’ll prepare, send, and track for you when you’re ready",
    subtitle:
      "This step covers the guided package for your round—mailing, tracking, and structured follow-through—not a separate fee to “get” the letters. You can still download them in the app. Nothing is physically mailed at checkout; you stay in control of the next step.",
  } as const;

  const orionAuthority = useMemo(
    () => resolveOrionAuthority(orionViewModel, integrityHints),
    [orionViewModel, integrityHints],
  );

  const paymentHero = useMemo(
    () => orionStepHeroCopy(orionAuthority, orionViewModel, PAYMENT_HERO_FALLBACK),
    [orionAuthority, orionViewModel],
  );

  const checkoutEmphasisClass = paymentRecommendedCheckoutButtonClass(paymentHero.ctaEmphasis);

  const paymentSuccess = searchParams.get("payment") === "success";
  const paymentCancelled = searchParams.get("payment") === "cancelled";
  const sessionId = searchParams.get("session_id");

  const finalizeReconcile = useCallback(
    async (sid: string) => {
      if (!token || !workflowId) return;
      setReconcileBusy(true);
      setReconcileError(null);
      try {
        const r = await postPaymentReconcile(token, workflowId, sid);
        applyWorkflowEnvelope(r.workflow);
        const stepDone = r.reconcile.paymentStepCompleted !== false;
        if (!stepDone) {
          setPaymentStepPending(true);
          return;
        }
        setPaymentStepPending(false);
        reconciledSidRef.current = sid;
        setSearchParams({}, { replace: true });
        navigate(customerPathFromEnvelope(r.workflow), { replace: true });
        void load();
      } catch (e) {
        setReconcileError(e instanceof Error ? e.message : String(e));
      } finally {
        setReconcileBusy(false);
      }
    },
    [token, workflowId, applyWorkflowEnvelope, navigate, setSearchParams, load],
  );

  useEffect(() => {
    if (!paymentSuccess || !sessionId || !token || !workflowId) return;
    if (reconciledSidRef.current === sessionId) return;
    void finalizeReconcile(sessionId);
  }, [paymentSuccess, sessionId, token, workflowId, finalizeReconcile]);

  const clearQuery = () => {
    setSearchParams({}, { replace: true });
  };

  const startCheckout = async (productId: string) => {
    if (!token || !workflowId) return;
    setCheckoutLoadingId(productId);
    try {
      const r = await postPaymentCheckout(token, workflowId, productId);
      applyWorkflowEnvelope(r.workflow);
      const url = r.checkoutUrl;
      if (url) {
        window.location.assign(url);
        return;
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCheckoutLoadingId(null);
    }
  };

  const continueWithCredits = async () => {
    if (!token || !workflowId) return;
    setCreditsLoading(true);
    setError(null);
    try {
      const r = await postPaymentContinueWithCredits(token, workflowId);
      applyWorkflowEnvelope(r.workflow);
      navigate(customerPathFromEnvelope(r.workflow), { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreditsLoading(false);
    }
  };

  const canActOnPaymentStep =
    !!pay?.onPaymentStep && authoritativeStepId === "payment" && !loading;
  const stripeGo =
    !!pay?.stripeCheckoutAvailable &&
    !!pay?.checkoutReturnOriginConfigured &&
    canActOnPaymentStep;
  const canUseCredits = canActOnPaymentStep && !!pay?.hasSufficientLetterEntitlement;

  return (
    <div
      className="relative min-h-full bg-lab-bg"
      data-orion-fallback={orionViewModel.fallbackMode}
    >
      <StepPageAmbientBackground />

      <TopBarMinimal />

      <StepMainColumn
        className={`relative z-10 mx-auto max-w-xl px-4 pb-24 sm:px-6 sm:pb-28 ${stepMainColumnTopClass(!!workflowId)}`}
      >
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          <motion.h2 variants={headerVariants} className="step-title">
            {paymentHero.title}
          </motion.h2>
          <motion.p variants={headerVariants} className="step-support">
            {paymentHero.subtitle}
          </motion.p>

          {!loading && pay?.onPaymentStep ? (
            <motion.div
              variants={headerVariants}
              className="surface-emerald-reassure mx-auto mt-6 max-w-lg"
            >
              <ul className="space-y-2 text-left text-sm leading-relaxed text-emerald-50/95 sm:text-[15px]">
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>Your download and review in the app stay available — you&apos;re not “buying a PDF” as the product</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>Payment is for the guided path: package prep, optional send, and ongoing tracking as you use it</span>
                </li>
                <li className="flex gap-2">
                  <span className="mt-0.5 shrink-0 text-emerald-300" aria-hidden>
                    •
                  </span>
                  <span>Nothing is put in the mail at this step — you confirm each send later</span>
                </li>
              </ul>
            </motion.div>
          ) : null}

          {!loading && pay?.onPaymentStep ? <PaymentNextStepsStrip /> : null}

          {loading ? (
            <motion.p variants={headerVariants} className="mt-10 text-center text-sm text-lab-muted">
              Loading your payment options…
            </motion.p>
          ) : null}

          {error ? (
            <motion.p variants={headerVariants} className="mt-8 text-center text-sm text-red-300/90">
              {error}
            </motion.p>
          ) : null}

          {paymentCancelled ? (
            <motion.div
              variants={headerVariants}
              className="mt-8 rounded-lg border border-white/[0.1] bg-lab-surface/80 p-4 text-center text-sm text-lab-muted"
            >
              <p className="font-medium text-lab-text">Checkout was not completed yet</p>
              <p className="mt-2">Your round is still saved and ready. You can return here when you want to continue.</p>
              <button
                type="button"
                onClick={clearQuery}
                className="mt-3 text-sm font-medium text-lab-accent hover:text-lab-accent/90"
              >
                Dismiss
              </button>
            </motion.div>
          ) : null}

          {paymentSuccess && sessionId ? (
            <motion.div
              variants={headerVariants}
              className="mt-8 rounded-xl border border-white/[0.1] bg-lab-surface/90 px-4 py-4 text-center sm:px-5"
            >
              {reconcileBusy ? (
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-lab-text">Your payment is being confirmed…</p>
                  <p className="text-sm text-lab-muted">
                    Connecting your checkout to this program — usually just a few seconds.
                  </p>
                  <p className="text-xs text-lab-subtle">{NEXT_STEP_AFTER_PAYMENT_LINE}</p>
                </div>
              ) : paymentStepPending ? (
                <div className="space-y-3 text-left text-amber-100/95">
                  <p className="text-center text-sm font-semibold text-amber-50">
                    Almost there — one more step
                  </p>
                  <p className="text-center text-sm text-amber-100/90">
                    Your payment went through; this screen is still catching up. Tap below to finish
                    — safe to try again if needed.
                  </p>
                  <p className="text-center text-xs text-amber-200/80">{NEXT_STEP_AFTER_PAYMENT_LINE}</p>
                  <button
                    type="button"
                    disabled={!token || !workflowId || reconcileBusy}
                    onClick={() => void finalizeReconcile(sessionId)}
                    className="w-full rounded-lg border border-amber-400/40 py-2.5 text-sm font-semibold text-amber-50 hover:bg-amber-500/10 disabled:opacity-50"
                  >
                    Finish activating
                  </button>
                </div>
              ) : reconcileError ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-lab-text">Payment received — confirmation hit a snag</p>
                  <p className="text-sm text-red-300/90">{reconcileError}</p>
                  <p className="text-xs text-lab-subtle">
                    Your Stripe payment may still be valid. Retry, or contact support with your
                    program id if this keeps appearing.
                  </p>
                  <button
                    type="button"
                    disabled={!token || !workflowId || reconcileBusy}
                    onClick={() => void finalizeReconcile(sessionId)}
                    className="text-sm font-semibold text-lab-accent hover:text-zinc-100 disabled:opacity-50"
                  >
                    Retry confirmation
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-lab-muted">Your payment is being confirmed…</p>
                  <p className="text-xs text-lab-subtle">{NEXT_STEP_AFTER_PAYMENT_LINE}</p>
                </div>
              )}
            </motion.div>
          ) : null}

          {!loading && pay && !pay.onPaymentStep ? (
            <motion.div
              variants={headerVariants}
              className="mt-10 space-y-3 text-center text-sm text-lab-muted"
            >
              {pay.paymentStepCompleted ? (
                <>
                  <p>Payment is already complete for this program.</p>
                  <Link
                    to={canonicalCustomerPath}
                    className="inline-block font-semibold text-lab-accent hover:text-zinc-100"
                  >
                    Continue in your program →
                  </Link>
                </>
              ) : (
                <p>
                  This screen isn’t the active step right now. Your round stays saved — use{" "}
                  <Link
                    to={canonicalCustomerPath}
                    className="font-semibold text-lab-accent hover:text-zinc-100"
                  >
                    your current step
                  </Link>{" "}
                  to pick up where you left off.
                </p>
              )}
            </motion.div>
          ) : null}

          {!loading && pay && pay.onPaymentStep ? (
            <>
              <motion.div variants={headerVariants} className="mt-8 rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-6 shadow-xl shadow-black/25 sm:px-7 sm:py-8">
                <PreparedItemsSummary
                  categories={buildCategories(pay)}
                  title="Your current round"
                  description="This covers hands-off mailing, delivery tracking, and the structured run — not a fee for the letter files themselves."
                />

                <div className="my-7 border-t border-white/[0.06] sm:my-8" />

                <p className="text-xs font-medium uppercase tracking-[0.12em] text-lab-subtle">
                  Included in this step
                </p>
                <div className="mt-3">
                  <ValueRecapList
                    title="What this payment includes"
                    lines={[...PAYMENT_WHAT_HAPPENS_NEXT_LINES]}
                  />
                </div>

                <div className="mt-5 text-center text-xs text-lab-subtle">
                  Letter credits on your account:{" "}
                  <span className="font-medium text-lab-text">{pay.entitlements.letters}</span>
                </div>

                <div className="mt-8 space-y-3">
                  <p className="text-xs font-medium uppercase tracking-[0.12em] text-lab-subtle">
                    Recommended for this round
                  </p>
                  <div className="rounded-lg border border-zinc-700/45 bg-lab-bg/20 px-4 py-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-semibold text-lab-text">
                        {pay.recommendedPack.label}
                      </span>
                      <span className="text-sm font-semibold text-lab-accent">
                        {formatUsd(pay.recommendedPack.price_cents)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-lab-muted">
                      {pay.recommendedPack.ai_rounds} AI rounds · {pay.recommendedPack.letters} letters ·{" "}
                      {pay.recommendedPack.mailings} mailing balance (for certified send when you choose to)
                    </p>

                    <div className="mt-5 border-t border-white/[0.06] pt-4">
                      <p className="text-center text-sm font-semibold text-lab-text">
                        Continue and skip the manual busywork
                      </p>
                      <p className="mt-2 text-center text-sm leading-relaxed text-lab-muted">
                        After checkout you move to letter and proof steps — you avoid packaging, guessing
                        addresses, and doing follow-up without a paper trail, while keeping download if you
                        want it.
                      </p>
                      <button
                        type="button"
                        disabled={!stripeGo || checkoutLoadingId !== null}
                        onClick={() => void startCheckout(pay.recommendedPack.id)}
                        className={checkoutEmphasisClass}
                      >
                        {checkoutLoadingId === pay.recommendedPack.id
                          ? "Opening secure checkout…"
                          : "Continue to secure checkout"}
                      </button>
                      <p className="mt-2 text-center text-xs text-lab-subtle">
                        You&apos;ll stay in control of the next steps after payment.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-5">
                  <PaymentShell
                    stripeReady={!!pay.stripeCheckoutAvailable}
                    returnOriginConfigured={!!pay.checkoutReturnOriginConfigured}
                  />
                </div>

                {pay.otherPacks.length > 0 ? (
                  <div className="mt-6 space-y-2">
                    <p className="text-xs font-medium uppercase tracking-[0.12em] text-lab-subtle">
                      Other options (same program)
                    </p>
                    <ul className="space-y-2">
                      {pay.otherPacks.map((pk) => (
                        <li
                          key={pk.id}
                          className="flex flex-col gap-2 rounded-lg border border-white/[0.08] px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div>
                            <p className="text-sm font-medium text-lab-text">{pk.label}</p>
                            <p className="text-xs text-lab-muted">
                              {pk.ai_rounds} AI · {pk.letters} letters · {pk.mailings} mailings
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-3">
                            <span className="text-sm font-semibold text-lab-text">
                              {formatUsd(pk.price_cents)}
                            </span>
                            <button
                              type="button"
                              disabled={!stripeGo || checkoutLoadingId !== null}
                              onClick={() => void startCheckout(pk.id)}
                              className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-semibold text-lab-text transition-colors hover:bg-white/[0.06] disabled:pointer-events-none disabled:opacity-50"
                            >
                              {checkoutLoadingId === pk.id ? "…" : "Choose"}
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                {pay.alaCarteLetters.length > 0 ? (
                  <div className="mt-6 space-y-2">
                    <p className="text-xs font-medium uppercase tracking-[0.12em] text-lab-subtle">
                      À la carte letters
                    </p>
                    <ul className="space-y-2">
                      {pay.alaCarteLetters.map((a) => (
                        <li
                          key={a.id}
                          className="flex flex-col gap-2 rounded-lg border border-white/[0.08] px-3 py-3 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <span className="text-sm text-lab-text">{a.label}</span>
                          <div className="flex shrink-0 items-center gap-3">
                            <span className="text-sm font-semibold text-lab-text">
                              {formatUsd(a.price_cents)}
                            </span>
                            <button
                              type="button"
                              disabled={!stripeGo || checkoutLoadingId !== null}
                              onClick={() => void startCheckout(a.id)}
                              className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-semibold text-lab-text transition-colors hover:bg-white/[0.06] disabled:pointer-events-none disabled:opacity-50"
                            >
                              {checkoutLoadingId === a.id ? "…" : "Choose"}
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}

                <div className="mt-6 border-t border-white/[0.06] pt-6">
                  <button
                    type="button"
                    disabled={!canUseCredits || creditsLoading}
                    onClick={() => void continueWithCredits()}
                    className="w-full rounded-xl border border-white/15 py-3.5 text-[15px] font-semibold text-lab-text transition-colors hover:bg-white/[0.05] disabled:pointer-events-none disabled:opacity-50"
                  >
                    {creditsLoading ? "Continuing…" : "Use credits and continue"}
                  </button>
                  <p className="mt-2 text-center text-xs text-lab-subtle">
                    This round needs {pay.neededLetters} letter credit
                    {pay.neededLetters === 1 ? "" : "s"}. You have {pay.entitlements.letters} on your
                    account. When you already have enough credits, there&apos;s no extra charge — we
                    just move you forward.
                  </p>
                </div>
              </motion.div>
            </>
          ) : null}
        </motion.div>
      </StepMainColumn>
    </div>
  );
}
