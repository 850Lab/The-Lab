import { type FormEvent, useCallback, useEffect, useState } from "react";
import { getOrgMembers, postOrgMember, type OrgMemberRow } from "@/lib/orgProgramApi";

type Props = {
  token: string;
  orgId: number;
  /** Called after a successful add (refresh parent lists). */
  onRosterChanged?: () => void;
};

const ROLE_OPTIONS: { value: "org_user" | "org_instructor"; label: string; hint: string }[] = [
  { value: "org_user", label: "Participant", hint: "Moves through the program with the cohort." },
  { value: "org_instructor", label: "Co-guide", hint: "Hosts, sees the desk, can shape the room." },
];

function roleLabel(role: string): string {
  if (role === "org_user") return "Participant";
  if (role === "org_instructor") return "Guide";
  if (role === "org_admin") return "Org lead";
  return role;
}

export function OrgRosterInvitePanel({ token, orgId, onRosterChanged }: Props) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"org_user" | "org_instructor">("org_user");
  const [enrollInProgram, setEnrollInProgram] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [members, setMembers] = useState<OrgMemberRow[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);

  const loadMembers = useCallback(async () => {
    if (!token || !orgId) return;
    setLoadingMembers(true);
    try {
      const out = await getOrgMembers(token, orgId);
      setMembers(out.members ?? []);
    } catch {
      setMembers([]);
    } finally {
      setLoadingMembers(false);
    }
  }, [token, orgId]);

  useEffect(() => {
    void loadMembers();
  }, [loadMembers]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const em = email.trim().toLowerCase();
    if (!em) {
      setErr("Enter the email they used to sign up.");
      return;
    }
    setBusy(true);
    setErr(null);
    setOk(null);
    try {
      await postOrgMember(token, orgId, {
        email: em,
        role,
        enrollInProgram: role === "org_user" ? enrollInProgram : false,
      });
      setEmail("");
      setOk(
        role === "org_user" && enrollInProgram
          ? "Added to the organization and enrolled in the program."
          : "Added to the organization.",
      );
      await loadMembers();
      onRosterChanged?.();
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Could not add this person.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-white/10 bg-lab-surface p-5">
      <div>
        <h2 className="text-sm font-semibold text-lab-text">People & seats</h2>
        <p className="mt-1 text-xs leading-relaxed text-lab-muted">
          Add someone who <span className="text-lab-text/90">already has an account</span> (they must
          sign up first). You can place them in the cohort or bring in another guide — no developer
          or API steps required.
        </p>
      </div>

      {err && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-100" role="alert">
          {err}
        </div>
      )}
      {ok && (
        <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-2 text-xs text-emerald-100">
          {ok}
        </div>
      )}

      <form onSubmit={(ev) => void onSubmit(ev)} className="space-y-3">
        <label className="block text-sm">
          <span className="text-lab-muted">Their account email</span>
          <input
            type="email"
            autoComplete="off"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@organization.org"
            className="mt-1 w-full rounded-md border border-white/10 bg-lab-bg px-3 py-2 text-sm text-lab-text"
          />
        </label>
        <fieldset className="space-y-2">
          <legend className="text-xs font-medium text-lab-muted">Seat type</legend>
          {ROLE_OPTIONS.map((opt) => (
            <label
              key={opt.value}
              className="flex cursor-pointer gap-2 rounded-md border border-white/[0.06] px-3 py-2 text-sm"
            >
              <input
                type="radio"
                name="org-roster-role"
                value={opt.value}
                checked={role === opt.value}
                onChange={() => setRole(opt.value)}
                className="mt-1"
              />
              <span>
                <span className="font-medium text-lab-text">{opt.label}</span>
                <span className="mt-0.5 block text-xs text-lab-muted">{opt.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {role === "org_user" && (
          <label className="flex cursor-pointer items-start gap-2 text-sm text-lab-muted">
            <input
              type="checkbox"
              checked={enrollInProgram}
              onChange={(e) => setEnrollInProgram(e.target.checked)}
              className="mt-1"
            />
            <span>
              <span className="text-lab-text">Enroll in the program</span>
              <span className="mt-0.5 block text-xs">
                They appear on your cohort roster and can open the participant journey.
              </span>
            </span>
          </label>
        )}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md bg-violet-500/90 py-2.5 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-50"
        >
          {busy ? "Adding…" : "Add to organization"}
        </button>
      </form>

      <div className="border-t border-white/10 pt-4">
        <h3 className="text-xs font-medium uppercase tracking-wide text-lab-muted">Current team</h3>
        {loadingMembers ? (
          <p className="mt-2 text-xs text-lab-muted">Loading…</p>
        ) : members.length === 0 ? (
          <p className="mt-2 text-xs text-lab-muted">No members loaded.</p>
        ) : (
          <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-sm">
            {members.map((m) => {
              const label =
                (m.displayName || "").trim() ||
                (m.email || "").trim() ||
                `User #${m.userId}`;
              return (
                <li
                  key={m.id}
                  className="flex flex-wrap items-baseline justify-between gap-2 rounded border border-white/[0.04] px-2 py-1.5"
                >
                  <span className="text-lab-text">{label}</span>
                  <span className="text-xs text-lab-muted">{roleLabel(m.role)}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
