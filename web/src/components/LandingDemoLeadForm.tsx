import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import {
  buildProgramSignupHref,
  writeDemoProgramBridge,
} from "@/lib/demoProgramBridge";
import {
  DEMO_LANDING_INTENTS,
  showOrgAudienceFields,
  showReferrerField,
  type DemoLandingIntentValue,
} from "@/lib/demoLandingIntents";
import { submitPublicDemoLead } from "@/lib/publicDemoApi";
import type { PublicDemoRunResult } from "@/lib/publicDemoTypes";

type Props = {
  lastDemoRun: PublicDemoRunResult | null;
};

export function LandingDemoLeadForm({ lastDemoRun }: Props) {
  const [intent, setIntent] = useState<DemoLandingIntentValue | "">("");
  const [organizationName, setOrganizationName] = useState("");
  const [audienceNote, setAudienceNote] = useState("");
  const [referrerName, setReferrerName] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = useCallback(async () => {
    setErr(null);
    setBusy(true);
    try {
      await submitPublicDemoLead({
        name,
        email,
        phone,
        scenarioId: lastDemoRun?.scenarioId,
        workflowId: lastDemoRun?.workflowId,
        intent: intent || undefined,
        organizationName: organizationName.trim() || undefined,
        audienceNote: audienceNote.trim() || undefined,
        referrerName: referrerName.trim() || undefined,
      });
      writeDemoProgramBridge({
        scenarioId: lastDemoRun?.scenarioId,
        workflowId: lastDemoRun?.workflowId,
        source: "demo_lead",
      });
      setDone(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [
    name,
    email,
    phone,
    lastDemoRun,
    intent,
    organizationName,
    audienceNote,
    referrerName,
  ]);

  if (done) {
    return (
      <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.08] px-5 py-8 text-center sm:px-7">
        <p className="text-lg font-semibold text-lab-text">Thanks — we&apos;ll be in touch</p>
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-lab-muted">
          We received your details and what you&apos;re exploring. If you wanted to run the full program on
          your own file, you can start whenever you&apos;re ready.
        </p>
        {intent === "try_myself" ? (
          <Link
            to={buildProgramSignupHref()}
            className="mt-6 inline-flex rounded-xl bg-lab-accent px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-lab-accent/20 hover:bg-sky-500"
          >
            Create your account
          </Link>
        ) : null}
      </div>
    );
  }

  return (
    <div
      id="lead-form"
      className="scroll-mt-28 rounded-2xl border border-white/[0.08] bg-lab-surface/50 px-5 py-8 sm:px-8"
    >
      <h2 className="text-lg font-semibold text-lab-text">Tell us who you are</h2>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">
        So we can follow up about a workshop, a class, your own report, or a referral — whichever fits.
      </p>

      <div className="mt-6 space-y-4">
        <div>
          <label htmlFor="landing-intent" className="text-xs font-medium text-lab-subtle">
            What brings you here?
          </label>
          <select
            id="landing-intent"
            value={intent}
            onChange={(e) => setIntent(e.target.value as DemoLandingIntentValue | "")}
            className="mt-1.5 w-full rounded-lg border border-white/[0.1] bg-lab-surface/90 px-3 py-2.5 text-sm text-lab-text outline-none focus:border-lab-accent/40"
          >
            <option value="">Select one…</option>
            {DEMO_LANDING_INTENTS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {intent && showOrgAudienceFields(intent) ? (
          <>
            <div>
              <label htmlFor="landing-org" className="text-xs font-medium text-lab-subtle">
                Organization or school (optional)
              </label>
              <input
                id="landing-org"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-white/[0.1] bg-lab-surface/90 px-3 py-2.5 text-sm text-lab-text outline-none focus:border-lab-accent/40"
                placeholder="e.g. Community center, high school, credit union"
              />
            </div>
            <div>
              <label htmlFor="landing-audience" className="text-xs font-medium text-lab-subtle">
                Audience or group size (optional)
              </label>
              <textarea
                id="landing-audience"
                rows={2}
                value={audienceNote}
                onChange={(e) => setAudienceNote(e.target.value)}
                className="mt-1.5 w-full resize-y rounded-lg border border-white/[0.1] bg-lab-surface/90 px-3 py-2.5 text-sm text-lab-text outline-none focus:border-lab-accent/40"
                placeholder="Who you serve or expected headcount"
              />
            </div>
          </>
        ) : null}

        {intent && showReferrerField(intent) ? (
          <div>
            <label htmlFor="landing-referrer" className="text-xs font-medium text-lab-subtle">
              Who are you referring? (optional)
            </label>
            <input
              id="landing-referrer"
              value={referrerName}
              onChange={(e) => setReferrerName(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-white/[0.1] bg-lab-surface/90 px-3 py-2.5 text-sm text-lab-text outline-none focus:border-lab-accent/40"
              placeholder="Name or organization"
            />
          </div>
        ) : null}

        <div>
          <label htmlFor="landing-name" className="text-xs font-medium text-lab-subtle">
            Name
          </label>
          <input
            id="landing-name"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-white/[0.1] bg-lab-surface/90 px-3 py-2.5 text-sm text-lab-text outline-none focus:border-lab-accent/40"
            placeholder="Your name"
          />
        </div>
        <div>
          <label htmlFor="landing-email" className="text-xs font-medium text-lab-subtle">
            Email
          </label>
          <input
            id="landing-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-white/[0.1] bg-lab-surface/90 px-3 py-2.5 text-sm text-lab-text outline-none focus:border-lab-accent/40"
            placeholder="you@example.org"
          />
        </div>
        <div>
          <label htmlFor="landing-phone" className="text-xs font-medium text-lab-subtle">
            Phone
          </label>
          <input
            id="landing-phone"
            type="tel"
            autoComplete="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="mt-1.5 w-full rounded-lg border border-white/[0.1] bg-lab-surface/90 px-3 py-2.5 text-sm text-lab-text outline-none focus:border-lab-accent/40"
            placeholder="Best number to reach you"
          />
        </div>
      </div>

      {err ? <p className="mt-4 text-center text-sm text-red-300/90">{err}</p> : null}

      <button
        type="button"
        disabled={
          busy ||
          !intent ||
          name.trim().length < 2 ||
          email.trim().length < 5 ||
          phone.trim().length < 7
        }
        onClick={() => void submit()}
        className="mt-6 w-full rounded-xl bg-lab-accent py-3.5 text-[15px] font-semibold text-white shadow-lg shadow-lab-accent/20 outline-none transition-opacity focus-visible:ring-2 focus-visible:ring-lab-accent/40 disabled:opacity-45"
      >
        {busy ? "Sending…" : "Send"}
      </button>
      <p className="mt-3 text-center text-[11px] text-lab-subtle">
        We only use this to respond to your request.
      </p>
    </div>
  );
}
