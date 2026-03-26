export function PaymentShell() {
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
      <p className="mt-1 text-xs text-lab-subtle/90">
        Card details are encrypted. Stripe will appear here when connected.
      </p>
      <div className="mt-4 space-y-3" aria-hidden>
        <div className="h-10 rounded-md border border-white/[0.08] bg-lab-surface/50" />
        <div className="flex gap-3">
          <div className="h-10 flex-1 rounded-md border border-white/[0.08] bg-lab-surface/50" />
          <div className="h-10 w-24 rounded-md border border-white/[0.08] bg-lab-surface/50 sm:w-28" />
        </div>
      </div>
    </div>
  );
}
