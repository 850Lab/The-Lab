import { motion } from "framer-motion";
import { useCallback, useState } from "react";
import { submitPublicDemoLead } from "@/lib/publicDemoApi";
import { WAITLIST_LEAD_INTENT } from "@/lib/productGates";

const fieldLight =
  "mt-1.5 w-full rounded-lg border border-neutral-200/90 bg-white px-3 py-2.5 text-sm text-neutral-950 outline-none transition-colors focus:border-neutral-400 focus:ring-2 focus:ring-neutral-300/40";

const fieldDark =
  "mt-1.5 w-full rounded-lg border border-white/[0.12] bg-lab-bg/60 px-3 py-2.5 text-sm text-lab-text outline-none transition-colors placeholder:text-lab-subtle focus:border-zinc-500/50 focus:ring-2 focus:ring-zinc-500/25";

function resolvedNameForApi(name: string, email: string): string {
  const t = name.trim();
  if (t.length >= 2) return t;
  const local = email.trim().split("@")[0]?.replace(/[.+_]/g, " ").trim() ?? "";
  return local.length >= 2 ? local : "";
}

export type WaitlistLeadFormProps = {
  /** `dark` matches lab landing surfaces; default `light` for legacy pages. */
  variant?: "light" | "dark";
};

export function WaitlistLeadForm({ variant = "light" }: WaitlistLeadFormProps) {
  const dark = variant === "dark";
  const labelCls = dark ? "text-xs font-semibold text-lab-muted" : "text-xs font-semibold text-neutral-500";
  const fieldCls = dark ? fieldDark : fieldLight;
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const submit = useCallback(async () => {
    setErr(null);
    const em = email.trim();
    const ph = phone.trim();
    const resolvedName = resolvedNameForApi(name, em);
    if (!em.includes("@") || em.length < 5) {
      setErr("Please enter a valid email.");
      return;
    }
    if (resolvedName.length < 2) {
      setErr("Add your name (or use an email with a recognizable address before @).");
      return;
    }
    if (ph.length < 7) {
      setErr("Please enter a phone number we can reach you on.");
      return;
    }
    setBusy(true);
    try {
      await submitPublicDemoLead({
        name: resolvedName,
        email: em,
        phone: ph,
        intent: WAITLIST_LEAD_INTENT,
        organizationName: organizationName.trim() || undefined,
      });
      setDone(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [name, email, phone, organizationName]);

  if (done) {
    return (
      <div
        className={
          dark
            ? "rounded-2xl border border-white/[0.1] bg-lab-surface/80 px-5 py-9 text-center shadow-2xl shadow-black/30 backdrop-blur-sm sm:px-8"
            : "rounded-2xl border border-neutral-200/90 bg-neutral-50 px-5 py-9 text-center shadow-sm sm:px-8"
        }
        data-testid="waitlist-success"
      >
        <p className={`text-lg font-bold ${dark ? "text-white" : "text-neutral-950"}`}>
          You&apos;re on the list
        </p>
        <p
          className={`mx-auto mt-3 max-w-md text-sm font-medium leading-relaxed ${dark ? "text-lab-muted" : "text-neutral-600"}`}
        >
          We&apos;ll email you when private access opens. Priority goes to serious users — no spam,
          no noise.
        </p>
      </div>
    );
  }

  return (
    <div
      id="waitlist"
      data-testid="waitlist-form"
      className={
        dark
          ? "scroll-mt-28 rounded-2xl border border-white/[0.1] bg-lab-surface/75 px-5 py-8 shadow-2xl shadow-black/35 backdrop-blur-sm sm:px-8"
          : "scroll-mt-28 rounded-2xl border border-neutral-200/90 bg-white px-5 py-8 shadow-[0_20px_60px_-28px_rgba(15,23,42,0.12)] sm:px-8"
      }
    >
      <h2 className={`text-lg font-bold ${dark ? "text-white" : "text-neutral-950"}`}>
        Save your spot
      </h2>
      <p
        className={`mt-2 text-sm font-medium leading-relaxed ${dark ? "text-lab-muted" : "text-neutral-600"}`}
      >
        Short list, real humans. Tell us where to reach you when the door opens.
      </p>

      <div className="mt-6 space-y-4">
        <div>
          <label htmlFor="waitlist-name" className={labelCls}>
            Name{" "}
            <span className={`font-normal ${dark ? "text-lab-subtle" : "text-neutral-400"}`}>
              (optional)
            </span>
          </label>
          <input
            id="waitlist-name"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={fieldCls}
            placeholder="How we should address you"
          />
        </div>
        <div>
          <label htmlFor="waitlist-email" className={labelCls}>
            Email
          </label>
          <input
            id="waitlist-email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={fieldCls}
            placeholder="you@example.org"
          />
        </div>
        <div>
          <label htmlFor="waitlist-phone" className={labelCls}>
            Phone
          </label>
          <input
            id="waitlist-phone"
            type="tel"
            autoComplete="tel"
            required
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className={fieldCls}
            placeholder="Direct line for early access"
          />
        </div>
        <div>
          <label htmlFor="waitlist-org" className={labelCls}>
            Organization{" "}
            <span className={`font-normal ${dark ? "text-lab-subtle" : "text-neutral-400"}`}>
              (optional)
            </span>
          </label>
          <input
            id="waitlist-org"
            value={organizationName}
            onChange={(e) => setOrganizationName(e.target.value)}
            className={fieldCls}
            placeholder="Company, firm, or affiliation"
          />
        </div>
      </div>

      {err ? (
        <p
          className={`mt-4 text-center text-sm ${dark ? "text-rose-300/90" : "text-red-600"}`}
          data-testid="waitlist-error"
        >
          {err}
        </p>
      ) : null}

      <motion.button
        type="button"
        disabled={busy}
        onClick={() => void submit()}
        whileHover={busy ? undefined : { scale: 1.03 }}
        whileTap={busy ? undefined : { scale: 0.97 }}
        transition={{ type: "spring", stiffness: 480, damping: 28 }}
        className={
          dark
            ? "mt-6 w-full rounded-xl bg-white py-3.5 text-[15px] font-semibold text-lab-bg shadow-[0_10px_28px_-10px_rgba(0,0,0,0.5)] outline-none ring-1 ring-white/15 transition-[box-shadow,background-color] duration-200 hover:bg-neutral-100 focus-visible:ring-2 focus-visible:ring-zinc-400/50 disabled:pointer-events-none disabled:opacity-45"
            : "mt-6 w-full rounded-xl bg-neutral-950 py-3.5 text-[15px] font-semibold text-white shadow-[0_10px_28px_-10px_rgba(0,0,0,0.45)] outline-none ring-1 ring-white/10 transition-[box-shadow,background-color] duration-200 hover:bg-neutral-900 hover:shadow-[0_14px_36px_-12px_rgba(0,0,0,0.42),0_0_24px_-8px_rgba(255,255,255,0.22)] focus-visible:ring-2 focus-visible:ring-neutral-400/50 disabled:pointer-events-none disabled:opacity-45"
        }
      >
        {busy ? "Sending…" : "Get in line"}
      </motion.button>
      <p
        className={`mt-3 text-center text-[11px] font-medium ${dark ? "text-lab-subtle" : "text-neutral-400"}`}
      >
        Encrypted in transit. We use this only to coordinate access — never sold.
      </p>
    </div>
  );
}
