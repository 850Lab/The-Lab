import { useState } from "react";
import { Link } from "react-router-dom";
import { postMeGenerateLetters } from "@/lib/orgProgramApi";
import type { GenerateLettersResponse } from "@/lib/orgProgramTypes";
import { PROGRAM_EYEBROW } from "@/lib/orgProgramRoutes";
import { useAuth } from "@/providers/AuthContext";

export function ProgramLettersPage() {
  const { token } = useAuth();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateLettersResponse | null>(null);

  const run = async () => {
    if (!token) return;
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await postMeGenerateLetters(token);
      setResult(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "We couldn't draft your letters just now");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
          {PROGRAM_EYEBROW}
        </p>
        <h1 className="mt-2 text-xl font-semibold text-lab-text">Letters, ready for you</h1>
        <p className="mt-1 text-sm text-lab-muted">
          We draft from the focus you saved — so your voice stays consistent and the program does the
          heavy lifting. If something blocks the draft, we&apos;ll tell you plainly.
        </p>
      </div>

      {err && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-50">
          <p className="font-medium text-amber-100">We couldn&apos;t finish the letters</p>
          <p className="mt-1 text-amber-100/85">{err}</p>
          <p className="mt-2 text-xs text-amber-100/70">
            Sometimes this is billing or credits on your account. We&apos;re here to help — reach out
            if it&apos;s unclear.
          </p>
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 p-5 text-sm">
          <p className="font-semibold text-emerald-100">Your letters are ready</p>
          <p className="mt-2 text-emerald-100/90">
            We shaped <span className="font-medium text-emerald-50">{result.selectedItemCount}</span>{" "}
            topic{result.selectedItemCount === 1 ? "" : "s"} into mail-ready drafts
            {(result.bureauKeys ?? []).length > 0
              ? ` for ${(result.bureauKeys ?? []).join(", ")}`
              : ""}
            .
          </p>
          <p className="mt-2 text-xs text-emerald-100/75">
            {result.letters?.length ?? 0} letter draft{(result.letters?.length ?? 0) === 1 ? "" : "s"}{" "}
            in this run — review and mail on your timeline; the program keeps your record straight.
          </p>
        </div>
      )}

      <button
        type="button"
        disabled={busy || !token}
        onClick={() => void run()}
        className="rounded-md bg-lab-accent px-5 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-40"
      >
        {busy ? "Drafting…" : result ? "Draft again" : "Draft my letters"}
      </button>

      <div className="flex gap-4 text-sm">
        <Link to="/program/progress" className="text-lab-accent hover:underline">
          See your path
        </Link>
        <Link to="/program" className="text-lab-muted hover:text-lab-text hover:underline">
          Hub
        </Link>
      </div>
    </div>
  );
}
