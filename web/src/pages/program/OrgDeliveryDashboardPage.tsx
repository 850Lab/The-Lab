import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  getMeOrgProgram,
  getOrgParticipants,
  getOrgProgressSummary,
  getOrgSessions,
  getOrgWorkshopDesk,
  patchOrgEnrollmentWorkshop,
  postInstructorOverride,
  postOrgEnrollmentSession,
  postOrgSession,
  patchOrgSession,
  type OrgParticipantRow,
  type OrgProgressSummary,
  type OrgSessionRow,
  type OrgWorkshopDeskResponse,
} from "@/lib/orgProgramApi";
import type { OrgProgramResponse } from "@/lib/orgProgramTypes";
import { programStageLabel } from "@/lib/orgProgramRoutes";
import { OrgRosterInvitePanel } from "@/components/OrgRosterInvitePanel";
import { useAuth } from "@/providers/AuthContext";

type Mode = "instructor" | "buyer";

function sessionExperienceLabel(state: string): string {
  const m: Record<string, string> = {
    draft: "In planning",
    scheduled: "On the calendar",
    active: "Live — room open",
    completed: "Wrapped",
  };
  return m[state] ?? state;
}

function flowPhaseLabel(phase: string): string {
  const m: Record<string, string> = {
    prepare: "Prepare",
    start: "Start",
    guide: "Guide",
    wrap: "Wrap",
  };
  return m[phase] ?? phase;
}

export function OrgDeliveryDashboardPage({ mode }: { mode: Mode }) {
  const { token } = useAuth();
  const [ctx, setCtx] = useState<OrgProgramResponse | null>(null);
  const [summary, setSummary] = useState<OrgProgressSummary | null>(null);
  const [sessions, setSessions] = useState<OrgSessionRow[]>([]);
  const [participants, setParticipants] = useState<OrgParticipantRow[]>([]);
  const [sessionName, setSessionName] = useState("");
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [desk, setDesk] = useState<OrgWorkshopDeskResponse | null>(null);
  const [deskLoading, setDeskLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const orgId = ctx?.membership?.organizationId;
  const role = ctx?.membership?.role ?? "";
  const title =
    mode === "instructor" ? "Your room, in one view" : "How your cohort is doing";
  const subtitle =
    mode === "instructor"
      ? "See people by name, know who needs you beside them, and host workshops with language that matches where the cohort actually is — not a spreadsheet."
      : "A calm read on momentum: who is moving, who is with you, and what the cohort feels — without living in admin tools.";

  const allowed =
    mode === "instructor"
      ? role === "org_instructor" || role === "org_admin"
      : role === "org_admin";

  const showWorkshopTools =
    allowed && (role === "org_instructor" || role === "org_admin");
  const canRunRoomOverrides = role === "org_instructor";

  const refreshDesk = useCallback(async () => {
    if (!token || !orgId || !selectedSessionId || !showWorkshopTools) {
      setDesk(null);
      return;
    }
    setDeskLoading(true);
    try {
      const d = await getOrgWorkshopDesk(token, orgId, selectedSessionId);
      setDesk(d);
    } catch {
      setDesk(null);
    } finally {
      setDeskLoading(false);
    }
  }, [token, orgId, selectedSessionId, showWorkshopTools]);

  const load = useCallback(async () => {
    if (!token || !orgId) return;
    setLoading(true);
    setErr(null);
    try {
      const [prog, parts, sess] = await Promise.all([
        getOrgProgressSummary(token, orgId),
        getOrgParticipants(token, orgId),
        getOrgSessions(token, orgId),
      ]);
      setSummary(prog);
      setSessions(sess.sessions ?? []);
      setParticipants(parts.participants ?? []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load organization data");
      setSummary(null);
      setParticipants([]);
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, [token, orgId]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    void (async () => {
      try {
        const o = await getMeOrgProgram(token);
        if (!cancelled) setCtx(o);
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "Could not load org context");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token]);

  useEffect(() => {
    if (!token || !orgId || !allowed) return;
    void load();
  }, [token, orgId, allowed, load]);

  useEffect(() => {
    if (sessions.length === 0) {
      setSelectedSessionId(null);
      return;
    }
    const active = sessions.find((s) => s.state === "active");
    setSelectedSessionId((prev) => {
      if (prev != null && sessions.some((s) => s.id === prev)) return prev;
      return active?.id ?? sessions[0]!.id;
    });
  }, [sessions]);

  useEffect(() => {
    if (!showWorkshopTools || selectedSessionId == null) {
      setDesk(null);
      setDeskLoading(false);
      return;
    }
    if (loading) return;
    void refreshDesk();
  }, [loading, participants, selectedSessionId, showWorkshopTools, refreshDesk]);

  const stuckHint = useMemo(() => {
    if (!summary?.countAtStep) return null;
    const upload = summary.countAtStep.upload ?? 0;
    const findings = summary.countAtStep.findings_ready ?? 0;
    if (upload + findings === 0) return null;
    return `${upload} still sharing their report, ${findings} waiting on understanding — natural places to stand beside people.`;
  }, [summary]);

  async function onPauseResume(p: OrgParticipantRow, pause: boolean) {
    if (!token || !orgId || !canRunRoomOverrides) return;
    setBusyId(p.userId);
    setErr(null);
    try {
      await postInstructorOverride(token, orgId, p.userId, {
        action: pause ? "pause" : "resume",
        reasonSafe: pause ? "Your guide paused the live program for the cohort." : undefined,
      });
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Override failed");
    } finally {
      setBusyId(null);
    }
  }

  async function onCreateSession() {
    if (!token || !orgId || !sessionName.trim()) return;
    setErr(null);
    try {
      await postOrgSession(token, orgId, sessionName.trim());
      setSessionName("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not create session");
    }
  }

  async function onSessionState(
    s: OrgSessionRow,
    state: "draft" | "scheduled" | "active" | "completed",
  ) {
    if (!token || !orgId) return;
    setErr(null);
    try {
      await patchOrgSession(token, orgId, s.id, { state });
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not update session");
    }
  }

  async function onAssignSession(p: OrgParticipantRow, sessionIdStr: string) {
    if (!token || !orgId || !showWorkshopTools) return;
    const sid =
      sessionIdStr === "" || sessionIdStr === "none" ? null : Number(sessionIdStr);
    if (sid != null && Number.isNaN(sid)) return;
    setBusyId(p.userId);
    setErr(null);
    try {
      await postOrgEnrollmentSession(token, orgId, p.enrollmentId, sid);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not assign session");
    } finally {
      setBusyId(null);
    }
  }

  async function onWorkshopToggle(
    p: OrgParticipantRow,
    field: "checkedIn" | "workshopComplete",
    value: boolean,
  ) {
    if (!token || !orgId || !showWorkshopTools) return;
    if (selectedSessionId == null || p.sessionId !== selectedSessionId) return;
    setBusyId(p.userId);
    setErr(null);
    try {
      await patchOrgEnrollmentWorkshop(token, orgId, p.enrollmentId, {
        checkedIn: field === "checkedIn" ? value : undefined,
        workshopComplete: field === "workshopComplete" ? value : undefined,
      });
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not update attendance");
    } finally {
      setBusyId(null);
    }
  }

  if (!token) {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-6">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-lab-muted">
          {mode === "instructor" ? "Guide desk" : "Organization overview"}
        </p>
        <h1 className="mt-2 text-lg font-semibold text-lab-text">Sign in required</h1>
        <p className="mt-2 text-sm text-lab-muted">
          This internal view is for signed-in hosts and guides. Use the program hub after you sign in.
        </p>
        <Link
          to="/login"
          className="mt-5 inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-sky-400"
        >
          Sign in
        </Link>
        <p className="mt-4 text-sm text-lab-muted">
          <Link to="/program" className="text-lab-accent hover:underline">
            Program entry
          </Link>
          {" · "}
          <Link to="/" className="text-lab-accent hover:underline">
            Home
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
          This space is for organization guides and leads. If you expected a cohort seat, ask your
          host for an invite to the right account — or use the consumer program from home.
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <Link
            to="/program"
            className="inline-flex rounded-md bg-lab-accent px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-sky-400"
          >
            Program hub
          </Link>
          <Link to="/" className="inline-flex items-center text-sm text-lab-accent hover:underline">
            Consumer home
          </Link>
        </div>
      </div>
    );
  }

  if (!allowed) {
    return (
      <div className="rounded-lg border border-white/10 bg-lab-surface p-5 text-sm text-lab-muted">
        <p className="font-medium text-lab-text">Wrong role for this page</p>
        <p className="mt-2">
          {mode === "instructor"
            ? "This space is for guides and org leads."
            : "This pulse is for organization leads."}
        </p>
        <Link to="/program" className="mt-4 inline-block text-lab-accent hover:underline">
          Back to hub
        </Link>
      </div>
    );
  }

  const sessionOptions = sessions.map((s) => (
    <option key={s.id} value={String(s.id)}>
      {s.name} ({s.state})
    </option>
  ));

  return (
    <div className="space-y-8">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-lab-muted">
          {ctx.organization?.name ?? "Organization"}
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-lab-text">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm text-lab-muted">{subtitle}</p>
      </div>

      {err && (
        <div
          className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100"
          role="alert"
        >
          {err}
        </div>
      )}

      {showWorkshopTools && orgId != null && token && (
        <OrgRosterInvitePanel token={token} orgId={orgId} onRosterChanged={() => void load()} />
      )}

      {loading && (
        <p className="text-sm text-lab-muted" role="status">
          Bringing your cohort into view…
        </p>
      )}

      {!loading && summary && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-white/10 bg-lab-surface p-4">
            <h2 className="text-sm font-semibold text-lab-text">Who is in the program</h2>
            <p className="mt-1 text-xs text-lab-subtle">
              Everyone shares the same milestone map — synchronized awareness for the whole cohort.
            </p>
            <p className="mt-2 text-2xl font-semibold text-lab-text">
              {summary.totalParticipants}{" "}
              <span className="text-base font-normal text-lab-muted">in the cohort</span>
            </p>
            {summary.percentCompletedAll != null && (
              <p className="mt-1 text-sm text-lab-muted">
                {summary.percentCompletedAll}% have letters ready to mail, together
              </p>
            )}
            {stuckHint && (
              <p className="mt-3 text-xs text-amber-100/90">{stuckHint}</p>
            )}
          </div>
          <div className="rounded-lg border border-white/10 bg-lab-surface p-4">
            <h2 className="text-sm font-semibold text-lab-text">Where people are in the story</h2>
            <ul className="mt-2 space-y-1 text-sm text-lab-muted">
              {Object.entries(summary.countAtStep).map(([k, v]) => (
                <li key={k} className="flex justify-between gap-4">
                  <span>{programStageLabel(k)}</span>
                  <span className="text-lab-text">{v}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {showWorkshopTools && !loading && sessions.some((s) => s.state === "active") && (
        <div
          className="rounded-lg border border-emerald-500/35 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-50"
          role="status"
        >
          <p className="font-semibold text-emerald-100">A workshop is live</p>
          <p className="mt-1 text-emerald-100/85">
            Keep this view open while you teach. Use the desk below for what to say and who still needs help.
          </p>
        </div>
      )}

      {showWorkshopTools && !loading && (
        <div className="rounded-lg border border-white/10 bg-lab-surface p-4">
          <h2 className="text-sm font-semibold text-lab-text">Workshops & rhythm</h2>
          <p className="mt-1 text-xs leading-relaxed text-lab-muted">
            <span className="text-lab-text/90">Plan → schedule → go live → close</span> matches how people
            actually experience the day. Pull people onto the roster, then{" "}
            <span className="text-lab-text/90">Open the room</span> and{" "}
            <span className="text-lab-text/90">Wrap</span> so the cohort feels one shared moment.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <input
              type="text"
              value={sessionName}
              onChange={(e) => setSessionName(e.target.value)}
              placeholder="e.g. Week 2 — Dispute letters live"
              className="min-w-[200px] flex-1 rounded-md border border-white/10 bg-lab-bg px-3 py-2 text-sm text-lab-text"
            />
            <button
              type="button"
              onClick={() => void onCreateSession()}
              className="rounded-md bg-lab-accent px-4 py-2 text-sm font-medium text-slate-950 hover:bg-sky-400"
            >
              Add workshop
            </button>
          </div>
          <ul className="mt-4 space-y-2 text-sm">
            {sessions.map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-white/[0.06] px-3 py-2"
              >
                <span className="text-lab-text">
                  <span className="font-medium">{s.name}</span>{" "}
                  <span className="text-lab-muted">· {sessionExperienceLabel(s.state)}</span>
                </span>
                <span className="flex flex-wrap gap-1">
                  {s.state !== "active" && s.state !== "completed" && (
                    <button
                      type="button"
                      onClick={() => void onSessionState(s, "active")}
                      className="rounded bg-emerald-500/20 px-2 py-1 text-xs font-medium text-emerald-100 hover:bg-emerald-500/30"
                    >
                      Open the room
                    </button>
                  )}
                  {s.state === "active" && (
                    <button
                      type="button"
                      onClick={() => void onSessionState(s, "completed")}
                      className="rounded bg-white/10 px-2 py-1 text-xs font-medium text-lab-text hover:bg-white/15"
                    >
                      Wrap session
                    </button>
                  )}
                </span>
              </li>
            ))}
            {sessions.length === 0 && (
              <li className="text-lab-muted">
                No workshops yet — add one before your next hosted event.
              </li>
            )}
          </ul>

          {sessions.length > 0 && (
            <div className="mt-4 border-t border-white/10 pt-4">
              <label className="text-xs font-medium uppercase tracking-wide text-lab-muted">
                Workshop you&apos;re hosting
              </label>
              <select
                className="mt-2 w-full max-w-md rounded-md border border-white/10 bg-lab-bg px-3 py-2 text-sm text-lab-text"
                value={selectedSessionId ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setSelectedSessionId(v ? Number(v) : null);
                }}
              >
                {sessionOptions}
              </select>
            </div>
          )}
        </div>
      )}

      {showWorkshopTools && !loading && selectedSessionId != null && (
        <div className="rounded-lg border border-sky-500/25 bg-sky-500/5 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold text-lab-text">Live instructor desk</h2>
            {deskLoading && (
              <span className="text-xs text-lab-muted" role="status">
                Refreshing roster…
              </span>
            )}
          </div>
          {desk && (
            <>
              <p className="mt-2 text-xs text-lab-muted">
                <span className="font-medium text-lab-text">
                  {flowPhaseLabel(desk.instructorFocus.flowPhase)}
                </span>
                {" · "}
                Focus step:{" "}
                <span className="text-lab-text">
                  {programStageLabel(desk.instructorFocus.recommendedGuideStep)}
                </span>
              </p>
              <p className="mt-2 text-sm font-medium text-sky-100/95">
                {desk.instructorFocus.headline}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-lab-text/90">
                {desk.instructorFocus.sayThis}
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-xs text-lab-muted">
                <div className="rounded border border-white/10 bg-lab-surface/80 px-3 py-2">
                  <p className="font-medium text-lab-text">On this roster</p>
                  <p className="mt-1 text-lg text-lab-text">{desk.totals.rosterCount}</p>
                </div>
                <div className="rounded border border-white/10 bg-lab-surface/80 px-3 py-2">
                  <p className="font-medium text-lab-text">Checked in</p>
                  <p className="mt-1 text-lg text-lab-text">{desk.totals.checkedInCount}</p>
                </div>
                <div className="rounded border border-white/10 bg-lab-surface/80 px-3 py-2">
                  <p className="font-medium text-lab-text">Marked workshop done</p>
                  <p className="mt-1 text-lg text-lab-text">
                    {desk.totals.workshopMarkedCompleteCount}
                  </p>
                </div>
                <div className="rounded border border-white/10 bg-lab-surface/80 px-3 py-2">
                  <p className="font-medium text-lab-text">Program complete</p>
                  <p className="mt-1 text-lg text-lab-text">{desk.totals.programCompleteCount}</p>
                </div>
              </div>
              {desk.instructorFocus.stuck.length > 0 && (
                <div className="mt-4 rounded-md border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-sm">
                  <p className="font-medium text-amber-100">People who may need you beside them</p>
                  <ul className="mt-2 list-inside list-disc text-amber-50/90">
                    {desk.instructorFocus.stuck.map((s) => (
                      <li key={s.userId}>
                        {s.displayLabel} — {programStageLabel(s.programCurrentStep)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
          {!deskLoading && !desk && (
            <p className="mt-2 text-sm text-lab-muted">Could not load desk for this session.</p>
          )}
        </div>
      )}

      {!loading && participants.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-white/10 bg-lab-surface">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-white/10 text-xs uppercase text-lab-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Participant</th>
                <th className="px-3 py-2 font-medium">Seat</th>
                <th className="px-3 py-2 font-medium">Their chapter</th>
                {showWorkshopTools && (
                  <th className="px-3 py-2 font-medium">Workshop</th>
                )}
                {showWorkshopTools && selectedSessionId != null && (
                  <>
                    <th className="px-3 py-2 font-medium">Here</th>
                    <th className="px-3 py-2 font-medium">Done today</th>
                  </>
                )}
                {canRunRoomOverrides && (
                  <th className="px-3 py-2 font-medium">Lead the room</th>
                )}
              </tr>
            </thead>
            <tbody>
              {participants.map((p) => {
                const label = p.displayLabel ?? p.displayName ?? p.email ?? `User #${p.userId}`;
                const inFocusSession =
                  selectedSessionId != null && p.sessionId === selectedSessionId;
                const step = p.programCurrentStep ?? "—";
                return (
                  <tr key={p.userId} className="border-b border-white/[0.06]">
                    <td className="px-3 py-2 text-lab-text">
                      <span className="font-medium">{label}</span>
                      {p.email && (
                        <span className="mt-0.5 block text-xs text-lab-muted">{p.email}</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-lab-muted">{p.enrollmentStatus}</td>
                    <td className="px-3 py-2 text-lab-text">{programStageLabel(step)}</td>
                    {showWorkshopTools && (
                      <td className="px-3 py-2">
                        <select
                          className="max-w-[200px] rounded border border-white/10 bg-lab-bg px-2 py-1 text-xs text-lab-text"
                          disabled={busyId === p.userId}
                          value={p.sessionId != null ? String(p.sessionId) : "none"}
                          onChange={(e) => void onAssignSession(p, e.target.value)}
                        >
                          <option value="none">Unassigned</option>
                          {sessions.map((s) => (
                            <option key={s.id} value={String(s.id)}>
                              {s.name}
                            </option>
                          ))}
                        </select>
                      </td>
                    )}
                    {showWorkshopTools && selectedSessionId != null && (
                      <>
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-sky-400"
                            disabled={busyId === p.userId || !inFocusSession}
                            checked={Boolean(p.sessionCheckedInAt)}
                            title={
                              inFocusSession
                                ? "Checked in for this workshop"
                                : "Assign this person to the focused workshop first"
                            }
                            onChange={(e) =>
                              void onWorkshopToggle(p, "checkedIn", e.target.checked)
                            }
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-emerald-400"
                            disabled={busyId === p.userId || !inFocusSession}
                            checked={Boolean(p.sessionWorkshopCompleteAt)}
                            title={
                              inFocusSession
                                ? "Marked finished for today’s hosted block"
                                : "Assign this person to the focused workshop first"
                            }
                            onChange={(e) =>
                              void onWorkshopToggle(p, "workshopComplete", e.target.checked)
                            }
                          />
                        </td>
                      </>
                    )}
                    {canRunRoomOverrides && (
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          <button
                            type="button"
                            disabled={busyId === p.userId}
                            onClick={() => void onPauseResume(p, true)}
                            title="Hold the cohort — everyone pauses together"
                            className="rounded bg-amber-500/20 px-2 py-1 text-xs text-amber-100 hover:bg-amber-500/30 disabled:opacity-50"
                          >
                            Hold room
                          </button>
                          <button
                            type="button"
                            disabled={busyId === p.userId}
                            onClick={() => void onPauseResume(p, false)}
                            title="Release the cohort to continue their steps"
                            className="rounded bg-emerald-500/20 px-2 py-1 text-xs text-emerald-100 hover:bg-emerald-500/30 disabled:opacity-50"
                          >
                            Release
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <Link
        to="/program"
        className="inline-block text-sm text-lab-accent hover:underline"
      >
        Back to hub
      </Link>
    </div>
  );
}
