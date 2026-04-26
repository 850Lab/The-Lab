import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  getMeProgress,
  isOrgProgramAbortError,
  pollMeReportParseJob,
  postMeAnalyze,
  postMeReport,
} from "@/lib/orgProgramApi";
import { PROGRAM_EYEBROW } from "@/lib/orgProgramRoutes";
import { useAuth } from "@/providers/AuthContext";
import { useOrionProgramAdvancement } from "@/hooks/useOrionProgramAdvancement";
import { ORION_BEHAVIOR } from "@/lib/orion/orionBehavior";
import type { OrionBehaviorStateId } from "@/lib/orion/orionBehavior";
import { useOrionSystem } from "@/providers/OrionSystemContext";

export function ProgramUploadPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [accessLocked, setAccessLocked] = useState(false);
  const [accessLoading, setAccessLoading] = useState(true);
  const [files, setFiles] = useState<File[]>([]);
  const [consent, setConsent] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [parseJob, setParseJob] = useState<{
    jobId: string;
    programWorkflowId: string;
  } | null>(null);
  const [analyzeBusy, setAnalyzeBusy] = useState(false);
  const [reportId, setReportId] = useState<number | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const parseBusy = parseJob != null;
  /** Bumps each time a parse-poll effect run starts; ignores stale async completions (Strict Mode + navigation). */
  const parsePollGenerationRef = useRef(0);
  const { setSurface, buildStrip } = useOrionSystem();

  const intakeFlowKey = useMemo(() => {
    if (parseBusy) return "INTAKE_PARSE_IN_PROGRESS" as const;
    if (reportId != null) return "INTAKE_AWAIT_ANALYZE" as const;
    return "INTAKE_OPEN" as const;
  }, [parseBusy, reportId]);

  const intakeAdvancement = useOrionProgramAdvancement({
    stateKey: intakeFlowKey,
    enabled: Boolean(intakeFlowKey) && !accessLocked && !accessLoading,
  });

  useEffect(() => {
    if (!accessLoading && accessLocked) {
      setSurface(null);
      return;
    }
    if (accessLoading) {
      setSurface(null);
      return;
    }

    let behaviorId: OrionBehaviorStateId = "INTAKE_OPEN";
    if (parseBusy) behaviorId = "INTAKE_PARSE_IN_PROGRESS";
    else if (reportId != null) behaviorId = "INTAKE_AWAIT_ANALYZE";

    const reportReceived = parseBusy || reportId != null;
    setSurface({
      stateKey: `intake-${behaviorId}`,
      behavior: ORION_BEHAVIOR[behaviorId],
      caseStrip: buildStrip({
        enrolled: true,
        reportAnalyzed: false,
        reviewSetPrepared: false,
        strategyStepActive: false,
      }),
      accentLine: reportReceived
        ? "Your file is held in this cohort until you start Case Review."
        : null,
    });

    return () => setSurface(null);
  }, [accessLoading, accessLocked, parseBusy, reportId, buildStrip, setSurface]);

  useEffect(() => {
    if (!token) {
      setAccessLoading(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const p = await getMeProgress(token);
        if (!cancelled) {
          setAccessLocked(Boolean(p.programAccess && !p.programAccess.allowed));
        }
      } catch {
        if (!cancelled) setAccessLocked(false);
      } finally {
        if (!cancelled) setAccessLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token || !parseJob) return;
    const runId = ++parsePollGenerationRef.current;
    const ac = new AbortController();
    void (async () => {
      try {
        const final = await pollMeReportParseJob(
          token,
          parseJob.programWorkflowId,
          parseJob.jobId,
          { signal: ac.signal },
        );
        if (runId !== parsePollGenerationRef.current) return;
        setParseJob(null);
        if (!final.ok || !final.reportIds?.length) {
          setErr(
            final.processingStatus === "failed"
              ? "Upload could not be processed."
              : "No report saved.",
          );
          return;
        }
        const rid = final.reportIds[0];
        setReportId(rid);
        setMsg("We have your report. One more step and we'll unpack what matters.");
      } catch (e) {
        if (isOrgProgramAbortError(e)) return;
        if (runId !== parsePollGenerationRef.current) return;
        setErr(e instanceof Error ? e.message : "Report processing failed");
        setParseJob(null);
      }
    })();
    return () => {
      ac.abort();
    };
  }, [token, parseJob?.jobId, parseJob?.programWorkflowId]);

  const onUpload = async () => {
    if (!token || files.length === 0) return;
    setUploadBusy(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await postMeReport(token, files, consent);
      setUploadBusy(false);

      if (res.processing && res.jobId && res.programWorkflowId) {
        setParseJob({ jobId: res.jobId, programWorkflowId: res.programWorkflowId });
        return;
      }

      if (!res.ok || !res.reportIds?.length) {
        throw new Error(
          res.processingStatus === "failed" ? "Upload could not be processed." : "No report saved.",
        );
      }
      const rid = res.reportIds[0];
      setReportId(rid);
      setMsg("We have your report. One more step and we'll unpack what matters.");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Upload failed");
      setUploadBusy(false);
    }
  };

  const onAnalyze = async () => {
    if (!token) return;
    setAnalyzeBusy(true);
    setErr(null);
    try {
      await postMeAnalyze(token, reportId);
      navigate("/program/findings");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "We couldn't finish reading your report");
    } finally {
      setAnalyzeBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
          {PROGRAM_EYEBROW}
        </p>
        <h1 className="mt-2 text-xl font-semibold text-lab-text">Share your bureau report</h1>
        <p className="mt-1 text-sm text-lab-muted">
          One bureau PDF is enough (or several parts under 25 MB each — we merge them into one
          report). We&apos;ll read it carefully and bring the important parts forward.
        </p>
      </div>

      {err && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
          {err}
        </div>
      )}
      {msg && (
        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
          {msg}
        </div>
      )}

      {accessLoading && (
        <p className="text-sm text-lab-muted" role="status">
          Checking that your program is open…
        </p>
      )}

      {!accessLoading && accessLocked && (
        <div
          className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-50"
          role="status"
        >
          <p className="font-medium text-amber-100">Your host is still opening the program</p>
          <p className="mt-1 text-amber-100/85">
            We&apos;re holding this space until your organization finishes activation — so your work
            always counts. Ask your admin to complete activation in Host setup, then come back here.
          </p>
          <Link
            to="/program"
            className="mt-3 inline-block text-sm text-amber-200 underline hover:text-amber-100"
          >
            Back to hub
          </Link>
        </div>
      )}

      <div
        className={`rounded-lg border border-dashed border-white/20 bg-lab-surface p-6 ${
          accessLocked || accessLoading ? "pointer-events-none opacity-40" : ""
        }`}
      >
        <label className="block text-sm font-medium text-lab-text">
          Bureau PDF (one file or multiple parts)
          <input
            type="file"
            accept="application/pdf,.pdf"
            multiple
            className="mt-2 block w-full text-sm text-lab-muted file:mr-4 file:rounded-md file:border-0 file:bg-lab-accent file:px-4 file:py-2 file:text-sm file:font-medium file:text-zinc-950"
            onChange={(e) => {
              const list = Array.from(e.target.files ?? []).sort((a, b) =>
                a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: "base" }),
              );
              setFiles(list);
            }}
          />
        </label>
        {files.length > 0 ? (
          <p className="mt-2 text-xs text-lab-subtle">
            {files.length} file{files.length === 1 ? "" : "s"} selected
            {files.length > 1 ? " · merged server-side in filename order" : ""}
          </p>
        ) : null}

        <label className="mt-4 flex cursor-pointer items-start gap-2 text-sm text-lab-muted">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5 rounded border-white/20 bg-lab-elevated"
          />
          <span>I agree to the privacy terms for sharing my report with this program.</span>
        </label>

        <button
          type="button"
          disabled={files.length === 0 || !consent || uploadBusy || parseBusy}
          onClick={() => void onUpload()}
          className="mt-6 w-full rounded-md bg-lab-accent py-2.5 text-sm font-semibold text-zinc-950 disabled:opacity-40 sm:w-auto sm:px-6"
        >
          {uploadBusy ? "Uploading…" : "Upload report"}
        </button>
      </div>

      {reportId != null && (
        <div className="space-y-4 rounded-lg border border-white/10 bg-lab-surface p-4">
          <button
            type="button"
            disabled={analyzeBusy || !intakeAdvancement.primaryActionEnabled}
            onClick={() => void onAnalyze()}
            className="rounded-md bg-lab-accent px-5 py-2 text-sm font-semibold text-zinc-950 transition-opacity duration-200 disabled:pointer-events-none disabled:opacity-35"
          >
            {analyzeBusy ? "Reading your report…" : "Read my report"}
          </button>
        </div>
      )}

      <Link
        to="/program/findings"
        className={`inline-block text-sm hover:underline ${
          accessLocked ? "pointer-events-none text-lab-muted/50" : "text-lab-accent"
        }`}
      >
        Already read? Open what we found
      </Link>
    </div>
  );
}
