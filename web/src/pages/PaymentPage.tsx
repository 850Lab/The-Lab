import { motion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { PaymentShell } from "@/components/PaymentShell";
import { PreparedItemsSummary, type PreparedCategory } from "@/components/PreparedItemsSummary";
import { PriceRow } from "@/components/PriceRow";
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
import { customerPathFromEnvelope } from "@/lib/workflowStepRoutes";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

function formatUsd(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}

const pageVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.04 },
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

function buildCategories(p: PaymentContextPayload): PreparedCategory[] {
  const out: PreparedCategory[] = [
    { label: "Dispute letters to generate (bureaus)", count: p.neededLetters },
  ];
  if (p.selectedDisputeItemCount != null) {
    out.unshift({
      label: "Dispute items selected",
      count: p.selectedDisputeItemCount,
    });
  }
  return out;
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
        <motion.div variants={pageVariants} initial="hidden" animate="show">
          <motion.p
            variants={headerVariants}
            className="text-center text-xs font-medium uppercase tracking-[0.14em] text-lab-subtle"
          >
            Activate
          </motion.p>
          <motion.h1
            variants={headerVariants}
            className="mt-3 text-center text-2xl font-semibold tracking-tight text-lab-text sm:text-[1.65rem]"
          >
            Complete payment
          </motion.h1>
          <motion.p
            variants={headerVariants}
            className="mx-auto mt-3 max-w-sm text-center text-sm leading-relaxed text-lab-muted sm:text-[15px]"
          >
            You’re buying letter credits (and mailings if included in the pack you pick). Checkout
            is handled by Stripe; this workflow stays linked to your purchase.
          </motion.p>

          {loading ? (
            <motion.p variants={headerVariants} className="mt-10 text-center text-sm text-lab-muted">
              Loading payment status…
            </motion.p>
          ) : null}

          {error ? (
            <motion.p variants={headerVariants} className="mt-8 text-center text-sm text-red-300/90">
              {error}
            </motion.p>
          ) : null}

          {paymentCancelled ? (
            <motion.div variants={headerVariants} className="mt-8 rounded-lg border border-white/[0.1] bg-lab-surface/80 p-4 text-center text-sm text-lab-muted">
              <p>Checkout was cancelled. You can choose a pack below when you’re ready.</p>
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
                  <p className="text-sm font-semibold text-lab-text">Payment received</p>
                  <p className="text-sm text-lab-muted">
                    Applying your purchase to this workflow (usually a few seconds).
                  </p>
                  <p className="text-xs text-lab-subtle">{NEXT_STEP_AFTER_PAYMENT_LINE}</p>
                </div>
              ) : paymentStepPending ? (
                <div className="space-y-3 text-left text-amber-100/95">
                  <p className="text-center text-sm font-semibold text-amber-50">
                    Purchase confirmed — one more tap
                  </p>
                  <p className="text-center text-sm text-amber-100/90">
                    Your credits are on your account; this workflow is still finishing the payment
                    step. Retry below — safe to run more than once.
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
                    workflow id if this keeps appearing.
                  </p>
                  <button
                    type="button"
                    disabled={!token || !workflowId || reconcileBusy}
                    onClick={() => void finalizeReconcile(sessionId)}
                    className="text-sm font-semibold text-lab-accent hover:text-sky-300 disabled:opacity-50"
                  >
                    Retry confirmation
                  </button>
                </div>
              ) : (
                <div className="space-y-2">
                  <p className="text-sm text-lab-muted">Confirming your purchase…</p>
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
                  <p>Payment is already complete for this workflow.</p>
                  <Link
                    to={canonicalCustomerPath}
                    className="inline-block font-semibold text-lab-accent hover:text-sky-300"
                  >
                    Go to your current step →
                  </Link>
                </>
              ) : (
                <p>
                  Payment isn’t the active step right now. Use{" "}
                  <Link
                    to={canonicalCustomerPath}
                    className="font-semibold text-lab-accent hover:text-sky-300"
                  >
                    your current step
                  </Link>{" "}
                  to continue.
                </p>
              )}
            </motion.div>
          ) : null}

          {!loading && pay && pay.onPaymentStep ? (
            <>
              <motion.div variants={headerVariants} className="mt-8 rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-6 shadow-xl shadow-black/25 sm:px-7 sm:py-8">
                <ValueRecapList lines={[...PAYMENT_WHAT_HAPPENS_NEXT_LINES]} />

                <div className="my-7 border-t border-white/[0.06] sm:my-8" />

                <PreparedItemsSummary categories={buildCategories(pay)} />

                <div className="mt-4 text-center text-xs text-lab-subtle">
                  Letter credits on your account:{" "}
                  <span className="font-medium text-lab-text">{pay.entitlements.letters}</span>
                </div>

                <div className="mt-6 space-y-3">
                  <p className="text-xs font-medium uppercase tracking-[0.12em] text-lab-subtle">
                    Recommended
                  </p>
                  <div className="rounded-lg border border-lab-accent/25 bg-lab-bg/20 px-4 py-3">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-semibold text-lab-text">
                        {pay.recommendedPack.label}
                      </span>
                      <span className="text-sm font-semibold text-lab-accent">
                        {formatUsd(pay.recommendedPack.price_cents)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-lab-muted">
                      {pay.recommendedPack.ai_rounds} AI · {pay.recommendedPack.letters} letters ·{" "}
                      {pay.recommendedPack.mailings} mailings
                    </p>
                    <button
                      type="button"
                      disabled={!stripeGo || checkoutLoadingId !== null}
                      onClick={() => void startCheckout(pay.recommendedPack.id)}
                      className="mt-3 w-full rounded-lg bg-lab-accent py-2.5 text-sm font-semibold text-white shadow-md shadow-lab-accent/20 disabled:pointer-events-none disabled:opacity-50"
                    >
                      {checkoutLoadingId === pay.recommendedPack.id
                        ? "Opening Stripe…"
                        : "Pay with Stripe"}
                    </button>
                  </div>
                </div>

                {pay.otherPacks.length > 0 ? (
                  <div className="mt-6 space-y-2">
                    <p className="text-xs font-medium uppercase tracking-[0.12em] text-lab-subtle">
                      Other packs
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

                <div className="mt-6">
                  <PriceRow label="Recommended total" amountDisplay={formatUsd(pay.recommendedPack.price_cents)} />
                </div>

                <div className="mt-6">
                  <PaymentShell
                    stripeReady={!!pay.stripeCheckoutAvailable}
                    returnOriginConfigured={!!pay.checkoutReturnOriginConfigured}
                  />
                </div>

                <div className="mt-6 border-t border-white/[0.06] pt-6">
                  <button
                    type="button"
                    disabled={!canUseCredits || creditsLoading}
                    onClick={() => void continueWithCredits()}
                    className="w-full rounded-xl border border-white/15 py-3.5 text-[15px] font-semibold text-lab-text transition-colors hover:bg-white/[0.05] disabled:pointer-events-none disabled:opacity-50"
                  >
                    {creditsLoading
                      ? "Continuing…"
                      : "Continue with my existing letter credits"}
                  </button>
                  <p className="mt-2 text-center text-xs text-lab-subtle">
                    Requires at least {pay.neededLetters} letter credit
                    {pay.neededLetters === 1 ? "" : "s"} for this round. You have{" "}
                    {pay.entitlements.letters}.
                  </p>
                </div>
              </motion.div>
            </>
          ) : null}
        </motion.div>
      </main>
    </div>
  );
}
