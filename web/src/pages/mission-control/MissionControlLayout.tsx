import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  getMissionControlAdminKey,
  setMissionControlAdminKey,
} from "@/lib/missionControlApi";

const nav = [
  ["Overview", "/mission-control"],
  ["Workflows", "/mission-control/workflows"],
  ["Exceptions", "/mission-control/exceptions"],
  ["Responses", "/mission-control/responses"],
  ["Reminders", "/mission-control/reminders"],
  ["Admin audit", "/mission-control/audit"],
];

export function MissionControlLayout() {
  const [keyInput, setKeyInput] = useState(getMissionControlAdminKey);
  const hasKey = keyInput.length > 0;

  return (
    <div className="min-h-full flex flex-col bg-lab-bg text-lab-text">
      <header className="border-b border-white/10 bg-lab-surface px-4 py-3 flex flex-wrap items-center gap-4">
        <div>
          <div className="text-xs font-bold uppercase tracking-widest text-lab-muted">
            Internal
          </div>
          <h1 className="text-lg font-semibold text-lab-text">
            Mission Control
          </h1>
        </div>
        <form
          className="flex flex-wrap items-center gap-2 ml-auto"
          onSubmit={(e) => {
            e.preventDefault();
            setMissionControlAdminKey(keyInput);
          }}
        >
          <label className="text-xs text-lab-muted whitespace-nowrap">
            Admin key
          </label>
          <input
            type="password"
            autoComplete="off"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="X-Workflow-Admin-Key"
            className="w-48 sm:w-64 rounded border border-white/15 bg-lab-elevated px-2 py-1.5 text-sm text-lab-text placeholder:text-lab-subtle focus:border-lab-accent/50 focus:outline-none"
          />
          <button
            type="submit"
            className="rounded bg-lab-accent/90 px-3 py-1.5 text-sm font-medium text-white hover:bg-lab-accent"
          >
            Save
          </button>
        </form>
        {!hasKey && (
          <p className="text-xs text-amber-200 w-full sm:w-auto">
            Set the admin API key to load data (same as WORKFLOW_ADMIN_API_SECRET).
          </p>
        )}
      </header>
      <div className="flex flex-1 min-h-0">
        <nav className="w-44 shrink-0 border-r border-white/10 bg-lab-surface p-2 space-y-0.5">
          {nav.map(([label, to]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/mission-control"}
              className={({ isActive }) =>
                `block rounded px-2 py-1.5 text-sm ${
                  isActive
                    ? "bg-lab-elevated text-lab-text font-medium"
                    : "text-lab-muted hover:text-lab-text hover:bg-lab-elevated/60"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <main className="flex-1 overflow-auto p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
