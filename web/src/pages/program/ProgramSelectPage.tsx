import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getMeDisputeOptions,
  postMeDisputeSelections,
} from "@/lib/orgProgramApi";
import type { DisputeOptionsResponse } from "@/lib/orgProgramTypes";
import { PROGRAM_EYEBROW } from "@/lib/orgProgramRoutes";
import { useAuth } from "@/providers/AuthContext";
import { ORION_BEHAVIOR } from "@/lib/orion/orionBehavior";
import { useOrionSystem } from "@/providers/OrionSystemContext";

function claimId(item: Record<string, unknown>): string {
  return String(item.review_claim_id ?? "");
}

export function ProgramSelectPage() {
  const { token } = useAuth();
  const { setSurface, buildStrip } = useOrionSystem();
  const [opt, setOpt] = useState<DisputeOptionsResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setOpt(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setErr(null);
      try {
        const o = await getMeDisputeOptions(token);
        if (cancelled) return;
        setErr(null);
        setOpt(o);
        const defs = o.disputeStrategy?.defaultSelectedReviewClaimIds ?? [];
        setSelected(new Set(defs.map(String)));
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Could not load dispute options");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token) {
      setSurface(null);
      return;
    }
    if (loading) {
      setSurface({
        stateKey: "strategy-load",
        behavior: ORION_BEHAVIOR.STRATEGY_LOADING,
        caseStrip: buildStrip({
          enrolled: true,
          reportAnalyzed: true,
          reviewSetPrepared: true,
          strategyStepActive: true,
        }),
      });
      return () => setSurface(null);
    }
    if (!opt?.selectionAllowed || !opt.disputeStrategy) {
      setSurface(null);
      return;
    }
    setSurface({
      stateKey: "strategy-workspace",
      behavior: ORION_BEHAVIOR.STRATEGY_PREPARE,
      caseStrip: buildStrip({
        enrolled: true,
        reportAnalyzed: true,
        reviewSetPrepared: true,
        strategyStepActive: true,
      }),
    });
    return () => setSurface(null);
  }, [token, loading, opt?.selectionAllowed, opt?.disputeStrategy, buildStrip, setSurface]);

  const reportId = opt?.reportId;
  const eligible = useMemo(
    () => new Set(opt?.disputeStrategy?.eligibleReviewClaimIds?.map(String) ?? []),
    [opt],
  );

  const toggle = (id: string) => {
    if (!eligible.has(id)) return;
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
    setSavedMsg(null);
  };

  const onSave = async () => {
    if (!token || reportId == null) return;
    const ids = [...selected].filter((x) => eligible.has(x));
    if (ids.length === 0) {
      setErr("Carry at least one prepared issue forward in your Review Set.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await postMeDisputeSelections(token, reportId, ids);
      setSavedMsg(
        "Saved what's included for this round. Your letters will follow this strategy set — continue when you're ready.",
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <p className="text-sm text-lab-muted" role="status">
        Opening your strategy workspace…
      </p>
    );
  }

  if (err && !opt) {
    return (
      <div className="rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
        <p className="font-medium text-red-100">We couldn&apos;t load your strategy workspace</p>
        <p className="mt-1 text-red-200/90">{err}</p>
        <p className="mt-2 text-sm text-red-200/75">
          Finish Case Review first, or your guide may have the room on hold.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link
            to="/program/upload"
            className="inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-zinc-950 hover:brightness-110"
          >
            Share your report
          </Link>
          <Link to="/program/findings" className="inline-flex items-center text-sm text-lab-accent hover:underline">
            What we found
          </Link>
          <Link to="/program" className="inline-flex items-center text-sm text-lab-muted hover:text-lab-text hover:underline">
            Hub
          </Link>
        </div>
      </div>
    );
  }

  if (!opt?.selectionAllowed || !opt.disputeStrategy) {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-6 text-sm">
        <p className="text-lab-text font-medium">This part of the program isn&apos;t open yet</p>
        <p className="mt-2 text-lab-muted">{opt?.selectionBlockedReason ?? "Check back soon."}</p>
        <Link to="/program/findings" className="mt-4 inline-block text-lab-accent hover:underline">
          Back to what we found
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
          {PROGRAM_EYEBROW}
        </p>
        <h1 className="mt-2 text-xl font-semibold text-lab-text">Strategy workspace</h1>
        <p className="mt-1 text-sm text-lab-muted">
          Your strategy is being prepared from your Review Set. These items were organized for you —
          use include or hold to confirm what carries into this round&apos;s correction plan. Only
          eligible items are shown.
        </p>
      </div>

      {err && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
          {err}
        </div>
      )}
      {savedMsg && (
        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
          {savedMsg}
        </div>
      )}

      <p className="text-xs font-medium uppercase tracking-wide text-lab-subtle">Prepared for strategy</p>

      <div className="space-y-4">
        {opt.disputeStrategy.groups.map((g) => (
          <div key={g.reviewType} className="rounded-lg border border-white/10 bg-lab-surface p-4">
            <h2 className="text-sm font-semibold capitalize text-lab-text">
              {g.reviewType.replace(/_/g, " ")}
            </h2>
            <ul className="mt-3 space-y-2">
              {g.items.map((item) => {
                const id = claimId(item);
                if (!id || !eligible.has(id)) return null;
                const included = selected.has(id);
                return (
                  <li key={id}>
                    <label className="flex cursor-pointer gap-3 rounded-md border border-white/[0.06] bg-lab-elevated/50 p-3 hover:bg-lab-elevated">
                      <input
                        type="checkbox"
                        checked={included}
                        onChange={() => toggle(id)}
                        className="mt-1 rounded border-white/20 bg-lab-bg"
                        aria-label={
                          included ? "Included in this round strategy" : "Held back from this round"
                        }
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm text-lab-text">
                          {String(item.summary ?? item.question ?? id)}
                        </span>
                        <span className="mt-1 block text-[11px] text-lab-muted">
                          {included
                            ? "Included in this round\u2019s correction plan."
                            : "Held from this round — not carried into letters until you include it."}
                        </span>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <button
          type="button"
          disabled={saving || reportId == null}
          onClick={() => void onSave()}
          className="rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-zinc-950 disabled:opacity-40"
        >
          {saving ? "Saving…" : "Proceed with strategy"}
        </button>
        <Link
          to="/program/letters"
          className="text-center text-sm font-medium text-lab-accent hover:underline sm:text-left"
        >
          Continue to letters
        </Link>
      </div>
    </div>
  );
}
