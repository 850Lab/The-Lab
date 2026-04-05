import type { MailStatusPayload } from "@/lib/mailTruthTypes";
import type { MailContextPayload } from "@/lib/mailTypes";

function toneForMailStatus(ms: MailStatusPayload): string {
  if (ms.primaryState === "sending_failed") {
    return "border-red-500/35 bg-red-500/10";
  }
  if (
    ms.primaryState === "send_blocked" ||
    ms.primaryState === "no_letters" ||
    ms.primaryState === "proof_required"
  ) {
    return "border-amber-500/35 bg-amber-500/10";
  }
  if (ms.primaryState === "sent_test") {
    return "border-amber-500/30 bg-amber-500/10";
  }
  return "border-white/[0.1] bg-lab-surface";
}

/**
 * Primary status from ``mail.mailStatus`` (GET mail/context). No client-side mail state math.
 */
export function MailTruthStatusCard({ mail }: { mail: MailContextPayload }) {
  const ms = mail.mailStatus;
  return (
    <section
      className={`mx-auto mt-5 max-w-sm rounded-xl border px-4 py-4 sm:px-5 ${toneForMailStatus(ms)}`}
      aria-labelledby="mail-truth-title"
    >
      <h2
        id="mail-truth-title"
        className="text-[15px] font-semibold leading-snug text-lab-text sm:text-base"
      >
        {ms.title}
      </h2>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">{ms.message}</p>

      <ul className="mt-4 space-y-1.5 border-t border-white/[0.08] pt-3 text-xs text-lab-subtle">
        <li>
          Dispute letters ready to mail:{" "}
          <span className="font-medium text-lab-text">
            {ms.lettersGenerated ? "Yes" : "Not yet"}
          </span>
        </li>
        <li>
          Government ID & proof of address:{" "}
          <span className="font-medium text-lab-text">
            {ms.proofComplete ? "On file" : "Still needed"}
          </span>
        </li>
        <li>
          Mailing balance (used at certified send):{" "}
          <span className="font-medium text-lab-text">
            {ms.mailingCreditsAvailable
              ? `${mail.mailingsBalance} ready — one credit per live bureau send`
              : "Add mailings before you submit — send is the spend moment"}
          </span>
        </li>
        <li>
          Certified send mode:{" "}
          <span className="font-medium text-lab-text">
            {ms.requiresLiveForCustomerSend && ms.isTestMode
              ? "Blocked — live mail key required"
              : ms.isTestMode
                ? "Test (no physical USPS letter)"
                : "Live USPS certified mail"}
          </span>
        </li>
        {ms.hasTracking ? (
          <li className="text-lab-muted">
            At least one bureau has USPS tracking (shows handoff and transit — not proof the bureau
            finished its review).
          </li>
        ) : null}
      </ul>
    </section>
  );
}
