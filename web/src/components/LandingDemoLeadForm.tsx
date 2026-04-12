import { motion } from "framer-motion";
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
  /** Marketing landing: white surface, black type, silver borders. */
  variant?: "dark" | "light";
};

const fieldDark =
  "mt-1.5 w-full rounded-lg border border-white/[0.1] bg-lab-surface/90 px-3 py-2.5 text-sm text-lab-text outline-none transition-colors focus:border-lab-accent/40";
const fieldLight =
  "mt-1.5 w-full rounded-lg border border-neutral-200/90 bg-white px-3 py-2.5 text-sm text-neutral-950 outline-none transition-colors focus:border-neutral-400 focus:ring-2 focus:ring-neutral-300/40";

export function LandingDemoLeadForm({ lastDemoRun, variant = "dark" }: Props) {
  const light = variant === "light";
  const field = light ? fieldLight : fieldDark;
  const labelCls = light ? "text-xs font-semibold text-neutral-500" : "text-xs font-medium text-lab-subtle";
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
      <div
        className={
          light
            ? "rounded-2xl border border-neutral-200/90 bg-neutral-50 px-5 py-8 text-center shadow-sm sm:px-7"
            : "rounded-2xl border border-emerald-500/25 bg-emerald-500/[0.08] px-5 py-8 text-center sm:px-7"
        }
      >
        <p className={light ? "text-lg font-bold text-neutral-950" : "text-lg font-semibold text-lab-text"}>
          Thanks — we&apos;ll be in touch
        </p>
        <p
          className={
            light
              ? "mx-auto mt-2 max-w-md text-sm font-medium leading-relaxed text-neutral-600"
              : "mx-auto mt-2 max-w-md text-sm leading-relaxed text-lab-muted"
          }
        >
          We received your details and what you&apos;re exploring. If you wanted to run the full program on
          your own file, you can start whenever you&apos;re ready.
        </p>
        {intent === "try_myself" ? (
          <Link
            to={buildProgramSignupHref()}
            className={
              light
                ? "mt-6 inline-flex rounded-xl bg-neutral-950 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-neutral-900/20 transition-colors hover:bg-neutral-800"
                : "mt-6 inline-flex rounded-xl bg-lab-accent px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-black/35 hover:brightness-110"
            }
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
      className={
        light
          ? "scroll-mt-28 rounded-2xl border border-neutral-200/90 bg-white px-5 py-8 shadow-[0_20px_60px_-28px_rgba(15,23,42,0.12)] sm:px-8"
          : "scroll-mt-28 rounded-2xl border border-white/[0.08] bg-lab-surface/50 px-5 py-8 sm:px-8"
      }
    >
      <h2 className={light ? "text-lg font-bold text-neutral-950" : "text-lg font-semibold text-lab-text"}>
        Tell us who you are
      </h2>
      <p className={light ? "mt-2 text-sm font-medium leading-relaxed text-neutral-600" : "mt-2 text-sm leading-relaxed text-lab-muted"}>
        Workshop, class, your report, or a referral — pick what fits. We&apos;ll take it from
        there.
      </p>

      <div className="mt-6 space-y-4">
        <div>
          <label htmlFor="landing-intent" className={labelCls}>
            What brings you here?
          </label>
          <select
            id="landing-intent"
            value={intent}
            onChange={(e) => setIntent(e.target.value as DemoLandingIntentValue | "")}
            className={field}
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
              <label htmlFor="landing-org" className={labelCls}>
                Organization or school (optional)
              </label>
              <input
                id="landing-org"
                value={organizationName}
                onChange={(e) => setOrganizationName(e.target.value)}
                className={field}
                placeholder="e.g. Community center, high school, credit union"
              />
            </div>
            <div>
              <label htmlFor="landing-audience" className={labelCls}>
                Audience or group size (optional)
              </label>
              <textarea
                id="landing-audience"
                rows={2}
                value={audienceNote}
                onChange={(e) => setAudienceNote(e.target.value)}
                className={`${field} resize-y`}
                placeholder="Who you serve or expected headcount"
              />
            </div>
          </>
        ) : null}

        {intent && showReferrerField(intent) ? (
          <div>
            <label htmlFor="landing-referrer" className={labelCls}>
              Who are you referring? (optional)
            </label>
            <input
              id="landing-referrer"
              value={referrerName}
              onChange={(e) => setReferrerName(e.target.value)}
              className={field}
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
          <label htmlFor="landing-email" className={labelCls}>
            Email
          </label>
          <input
            id="landing-email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={field}
            placeholder="you@example.org"
          />
        </div>
        <div>
          <label htmlFor="landing-phone" className={labelCls}>
            Phone
          </label>
          <input
            id="landing-phone"
            type="tel"
            autoComplete="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className={field}
            placeholder="Best number to reach you"
          />
        </div>
      </div>

      {err ? (
        <p className={light ? "mt-4 text-center text-sm text-red-600" : "mt-4 text-center text-sm text-red-300/90"}>
          {err}
        </p>
      ) : null}

      <motion.button
        type="button"
        disabled={
          busy ||
          !intent ||
          name.trim().length < 2 ||
          email.trim().length < 5 ||
          phone.trim().length < 7
        }
        onClick={() => void submit()}
        whileHover={
          busy ||
          !intent ||
          name.trim().length < 2 ||
          email.trim().length < 5 ||
          phone.trim().length < 7
            ? undefined
            : { scale: 1.03 }
        }
        whileTap={
          busy ||
          !intent ||
          name.trim().length < 2 ||
          email.trim().length < 5 ||
          phone.trim().length < 7
            ? undefined
            : { scale: 0.97 }
        }
        transition={{ type: "spring", stiffness: 480, damping: 28 }}
        className={
          light
            ? "mt-6 w-full rounded-xl bg-neutral-950 py-3.5 text-[15px] font-semibold text-white shadow-[0_10px_28px_-10px_rgba(0,0,0,0.45)] outline-none ring-1 ring-white/10 transition-[box-shadow,background-color] duration-200 hover:bg-neutral-900 hover:shadow-[0_14px_36px_-12px_rgba(0,0,0,0.42),0_0_24px_-8px_rgba(255,255,255,0.22)] focus-visible:ring-2 focus-visible:ring-neutral-400/50 disabled:pointer-events-none disabled:opacity-45"
            : "btn-primary-step mt-6 w-full disabled:pointer-events-none disabled:!opacity-[0.45]"
        }
      >
        {busy ? "Sending…" : "Send"}
      </motion.button>
      <p className={light ? "mt-3 text-center text-[11px] font-medium text-neutral-400" : "mt-3 text-center text-[11px] text-lab-subtle"}>
        We only use this to respond to your request.
      </p>
    </div>
  );
}
