/**
 * Client-only continuity hints from the public demo into signup/login.
 * Does not drive workflow progression — backend remains authoritative.
 */

export const DEMO_PROGRAM_ENTRY_DEFAULT_NEXT = "/get-report";

const STORAGE_KEY = "850lab_demo_program_bridge_v1";

export type DemoProgramBridgeSource =
  | "demo_welcome"
  | "demo_run"
  | "demo_lead"
  | "demo_unavailable";

export type DemoProgramBridge = {
  scenarioId?: string;
  workflowId?: string;
  source: DemoProgramBridgeSource;
  steppedAt: string;
};

export function writeDemoProgramBridge(
  partial: Omit<DemoProgramBridge, "steppedAt"> & { steppedAt?: string },
): void {
  try {
    const full: DemoProgramBridge = {
      ...partial,
      steppedAt: partial.steppedAt ?? new Date().toISOString(),
    };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(full));
  } catch {
    /* ignore */
  }
}

export function readDemoProgramBridge(): DemoProgramBridge | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const o = JSON.parse(raw) as Partial<DemoProgramBridge>;
    if (!o || typeof o !== "object" || typeof o.source !== "string") return null;
    return o as DemoProgramBridge;
  } catch {
    return null;
  }
}

export function isDemoContinuationSearch(search: string): boolean {
  try {
    const q = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
    return q.get("from") === "demo";
  } catch {
    return false;
  }
}

export function shouldShowDemoContinuationStrip(search: string): boolean {
  return isDemoContinuationSearch(search) || readDemoProgramBridge() != null;
}

export function buildProgramSignupHref(opts?: { next?: string }): string {
  const q = new URLSearchParams();
  q.set("from", "demo");
  q.set("next", opts?.next ?? DEMO_PROGRAM_ENTRY_DEFAULT_NEXT);
  return `/signup?${q.toString()}`;
}

export function buildProgramLoginHref(opts?: { next?: string }): string {
  const q = new URLSearchParams();
  q.set("from", "demo");
  q.set("next", opts?.next ?? DEMO_PROGRAM_ENTRY_DEFAULT_NEXT);
  return `/login?${q.toString()}`;
}
