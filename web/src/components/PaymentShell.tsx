type Props = {
  /** When true, checkout is configured server-side and the user will leave the app for Stripe. */
  stripeReady: boolean;
  returnOriginConfigured: boolean;
};

export function PaymentShell({ stripeReady, returnOriginConfigured }: Props) {
  return (
    <div className="rounded-lg border border-white/[0.08] bg-lab-bg/30 p-4 sm:p-5">
      <div className="flex items-center gap-2 text-xs text-lab-subtle">
        <svg
          className="h-3.5 w-3.5 shrink-0 text-lab-accent/80"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
          />
        </svg>
        <span>Secure card checkout</span>
      </div>
      {stripeReady && returnOriginConfigured ? (
        <p className="mt-2 text-xs leading-relaxed text-lab-muted sm:text-sm">
          Card details are entered on Stripe’s secure page. You’ll return here while we confirm the
          charge and unlock letter generation — not mail yet.
        </p>
      ) : (
        <p className="mt-2 text-xs leading-relaxed text-lab-muted sm:text-sm">
          {stripeReady
            ? "Stripe is connected, but the server must set WORKFLOW_CUSTOMER_APP_ORIGIN (or PUBLIC_APP_ORIGIN) so Stripe can redirect back to this app after payment."
            : "Stripe keys are not configured on the server — card checkout is unavailable until STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY (or Replit Stripe connector) are set."}
        </p>
      )}
    </div>
  );
}
