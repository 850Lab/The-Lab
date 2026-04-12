import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  getMeOrgProgram,
  getOrgProgramBilling,
  patchOrganization,
  postOrgProgramBillingReconcile,
  postOrgProgramCheckout,
  type OrgProgramBillingSnapshot,
} from "@/lib/orgProgramApi";
import type { OrgProgramResponse } from "@/lib/orgProgramTypes";
import { OrgRosterInvitePanel } from "@/components/OrgRosterInvitePanel";
import { useAuth } from "@/providers/AuthContext";

const STAGES = [
  { value: "draft", label: "Draft — just created" },
  { value: "profile", label: "Profile — contact details added" },
  { value: "instructor_ready", label: "Guide assigned" },
  { value: "live_ready", label: "Ready to host live workshops" },
] as const;

export function ProgramOrgSetupPage() {
  const { token, user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [ctx, setCtx] = useState<OrgProgramResponse | null>(null);
  const [contactEmail, setContactEmail] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [programCode, setProgramCode] = useState("");
  const [onboardingStage, setOnboardingStage] = useState("draft");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [billing, setBilling] = useState<OrgProgramBillingSnapshot | null>(null);
  const [billingErr, setBillingErr] = useState<string | null>(null);
  const [checkoutBusy, setCheckoutBusy] = useState(false);
  const [reconcileBusy, setReconcileBusy] = useState(false);

  const role = ctx?.membership?.role ?? "";
  const allowed = role === "org_instructor" || role === "org_admin";
  const orgId = ctx?.membership?.organizationId;
  const canRunCheckout = user?.role === "admin" || role === "org_admin";

  const loadBilling = useCallback(async () => {
    if (!token || !orgId || !allowed) return;
    try {
      const b = await getOrgProgramBilling(token, orgId);
      setBilling(b);
      setBillingErr(null);
    } catch (e) {
      setBilling(null);
      setBillingErr(e instanceof Error ? e.message : "Could not load billing");
    }
  }, [token, orgId, allowed]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    void (async () => {
      try {
        const o = await getMeOrgProgram(token);
        if (cancelled) return;
        setCtx(o);
        const org = o.organization;
        if (org) {
          setContactEmail(org.contactEmail ?? "");
          setContactPhone(org.contactPhone ?? "");
          setProgramCode(org.programCode ?? "850_lab_core");
          setOnboardingStage(org.onboardingStage ?? "draft");
        }
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "Could not load organization");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    void loadBilling();
  }, [loadBilling]);

  const paymentReturn = searchParams.get("payment");
  const stripeSessionQ = searchParams.get("session_id");

  useEffect(() => {
    if (paymentReturn !== "success" || !stripeSessionQ?.trim() || !token || !orgId) return;
    if (!canRunCheckout) return;
    let cancelled = false;
    setReconcileBusy(true);
    setBillingErr(null);
    void (async () => {
      try {
        await postOrgProgramBillingReconcile(token, orgId, stripeSessionQ.trim());
        if (!cancelled) {
          const o = await getMeOrgProgram(token);
          setCtx(o);
          await loadBilling();
          setSearchParams(
            (prev) => {
              const next = new URLSearchParams(prev);
              next.delete("payment");
              next.delete("session_id");
              return next;
            },
            { replace: true },
          );
          setMsg("You're all set — your cohort can move through the full program now.");
        }
      } catch (e) {
        if (!cancelled) {
          setBillingErr(e instanceof Error ? e.message : "Could not confirm payment");
        }
      } finally {
        if (!cancelled) setReconcileBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [paymentReturn, stripeSessionQ, token, orgId, canRunCheckout, loadBilling, setSearchParams]);

  async function onActivateProgram() {
    if (!token || !orgId || !canRunCheckout) return;
    setCheckoutBusy(true);
    setBillingErr(null);
    try {
      const out = await postOrgProgramCheckout(token, orgId);
      const url = out.checkoutUrl;
      if (url) {
        window.location.assign(url);
        return;
      }
      setBillingErr("Checkout could not be started.");
    } catch (e) {
      setBillingErr(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setCheckoutBusy(false);
    }
  }

  async function onSave() {
    if (!token || !orgId) return;
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      await patchOrganization(token, orgId, {
        contactEmail: contactEmail.trim() || undefined,
        contactPhone: contactPhone.trim() || undefined,
        programCode: programCode.trim() || undefined,
        onboardingStage: onboardingStage.trim() || undefined,
      });
      setMsg("Saved. Your organization profile is updated.");
      const o = await getMeOrgProgram(token);
      setCtx(o);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (!token) {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-6">
        <h1 className="text-lg font-semibold text-lab-text">Sign in to host setup</h1>
        <p className="mt-2 text-sm text-lab-muted">
          Billing, roster, and program activation for your organization are available after you sign
          in with an admin or guide account.
        </p>
        <Link
          to="/login"
          className="mt-5 inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-zinc-950 hover:brightness-110"
        >
          Sign in
        </Link>
        <p className="mt-4 text-sm text-lab-muted">
          <Link to="/program" className="text-lab-accent hover:underline">
            Program hub
          </Link>
        </p>
      </div>
    );
  }

  if (!ctx?.membership) {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-6">
        <h1 className="text-lg font-semibold text-lab-text">No organization on this account</h1>
        <p className="mt-2 text-sm text-lab-muted">
          Host setup opens when you belong to an organization as an admin or instructor. If you&apos;re
          a participant, use the program hub instead.
        </p>
        <Link
          to="/program"
          className="mt-5 inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-zinc-950 hover:brightness-110"
        >
          Go to program hub
        </Link>
      </div>
    );
  }

  if (!allowed) {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-5 text-sm text-lab-muted">
        <p className="font-medium text-lab-text">This setup is for hosts</p>
        <p className="mt-2">Ask your organization for a guide or admin seat to open this space.</p>
        <Link to="/program" className="mt-4 inline-block text-lab-accent hover:underline">
          Back to hub
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-lab-text">Host setup</h1>
        <p className="mt-2 text-sm text-lab-muted">
          Shape how your cohort experiences the program — not just settings, but the story people
          feel: who to call, which track you&apos;re running, and how ready the room is to open.
        </p>
      </div>

      <ol className="list-decimal space-y-2 pl-5 text-sm text-lab-muted">
        <li>Tell us how to reach your organization when it matters.</li>
        <li>Confirm the program track you&apos;re running (default: 850 Lab core).</li>
        <li>Move the onboarding stage as you assign guides and put live time on the calendar.</li>
      </ol>

      {orgId != null && token && (
        <OrgRosterInvitePanel token={token} orgId={orgId} />
      )}

      {err && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
          {err}
        </div>
      )}
      {msg && (
        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
          {msg}
        </div>
      )}

      {(billingErr || reconcileBusy) && (
        <div
          className={`rounded-md border p-3 text-sm ${
            reconcileBusy
              ? "border-white/15 bg-white/5 text-lab-muted"
              : "border-red-500/30 bg-red-500/10 text-red-100"
          }`}
          role="status"
        >
          {reconcileBusy ? "Confirming payment with Stripe…" : billingErr}
        </div>
      )}

      {billing && (
        <div className="space-y-3 rounded-lg border border-white/10 bg-lab-surface p-5">
          <h2 className="text-sm font-semibold text-lab-text">Access for your cohort</h2>
          <p className="text-xs leading-relaxed text-lab-muted">
            People can only move through the program when you&apos;ve opened the door — we pause
            gently until activation is complete so no one wastes effort.
          </p>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div className="rounded border border-white/[0.06] px-3 py-2">
              <dt className="text-xs text-lab-muted">Access status</dt>
              <dd className="mt-0.5 font-medium text-lab-text">
                {billing.programAccessAllowed ? "Active" : "Locked"}
              </dd>
              <dd className="text-xs text-lab-subtle">Plan state: {billing.paymentAccess}</dd>
            </div>
            <div className="rounded border border-white/[0.06] px-3 py-2">
              <dt className="text-xs text-lab-muted">Activated</dt>
              <dd className="mt-0.5 text-lab-text">
                {billing.programAccessActivatedAt
                  ? new Date(billing.programAccessActivatedAt).toLocaleString()
                  : "—"}
              </dd>
            </div>
            <div className="rounded border border-white/[0.06] px-3 py-2 sm:col-span-2">
              <dt className="text-xs text-lab-muted">Cohort pulse</dt>
              <dd className="mt-1 text-lab-text">
                {billing.usage.participantSeatsActive} active participant seats ·{" "}
                {billing.usage.programEnrollments ?? "—"} enrollments ·{" "}
                {billing.usage.reportsUploaded ?? 0} reports · {billing.usage.lettersGenerated ?? 0}{" "}
                letters
              </dd>
            </div>
          </dl>
          {canRunCheckout && !billing.programAccessAllowed && (
            <div className="mt-2 flex flex-col gap-2 border-t border-white/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-medium text-lab-text">{billing.catalog.label}</p>
                <p className="text-xs text-lab-muted">
                  ${(billing.catalog.priceCents / 100).toFixed(2)} one-time activation (unlock the
                  full hosted program for your cohort).
                </p>
              </div>
              <button
                type="button"
                disabled={checkoutBusy || reconcileBusy}
                onClick={() => void onActivateProgram()}
                className="rounded-md bg-lab-accent px-4 py-2.5 text-sm font-semibold text-zinc-950 hover:brightness-110 disabled:opacity-50"
              >
                {checkoutBusy ? "Redirecting…" : "Pay & activate program"}
              </button>
            </div>
          )}
          {canRunCheckout && billing.programAccessAllowed && (
            <p className="mt-2 text-xs text-emerald-100/90">
              The program is open. Your cohort can experience the full journey.
            </p>
          )}
          {!canRunCheckout && (
            <p className="mt-2 text-xs text-lab-muted">
              Only an organization admin (or platform operator) can run checkout. Ask your buyer
              seat to open Setup and activate.
            </p>
          )}
        </div>
      )}

      <div className="space-y-4 rounded-lg border border-white/10 bg-lab-surface p-5">
        <label className="block text-sm">
          <span className="text-lab-muted">Primary contact email</span>
          <input
            type="email"
            value={contactEmail}
            onChange={(e) => setContactEmail(e.target.value)}
            className="mt-1 w-full rounded-md border border-white/10 bg-lab-bg px-3 py-2 text-lab-text"
          />
        </label>
        <label className="block text-sm">
          <span className="text-lab-muted">Phone (optional)</span>
          <input
            type="tel"
            value={contactPhone}
            onChange={(e) => setContactPhone(e.target.value)}
            className="mt-1 w-full rounded-md border border-white/10 bg-lab-bg px-3 py-2 text-lab-text"
          />
        </label>
        <label className="block text-sm">
          <span className="text-lab-muted">Program code</span>
          <input
            type="text"
            value={programCode}
            onChange={(e) => setProgramCode(e.target.value)}
            className="mt-1 w-full rounded-md border border-white/10 bg-lab-bg px-3 py-2 text-lab-text"
          />
        </label>
        <label className="block text-sm">
          <span className="text-lab-muted">Onboarding stage</span>
          <select
            value={onboardingStage}
            onChange={(e) => setOnboardingStage(e.target.value)}
            className="mt-1 w-full rounded-md border border-white/10 bg-lab-bg px-3 py-2 text-lab-text"
          >
            {STAGES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={saving}
          onClick={() => void onSave()}
          className="w-full rounded-md bg-lab-accent py-2.5 text-sm font-semibold text-zinc-950 hover:brightness-110 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save and continue"}
        </button>
      </div>

      <p className="text-xs text-lab-muted">
        When you&apos;re ready: open the guide desk to host live time with your cohort.
      </p>

      <Link to="/program" className="inline-block text-sm text-lab-accent hover:underline">
        Back to hub
      </Link>
    </div>
  );
}
