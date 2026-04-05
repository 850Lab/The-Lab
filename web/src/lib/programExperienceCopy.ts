/**
 * Shared program voice: one guided experience, not a checklist of tools.
 * Use these labels everywhere participants see progression.
 */

export const PROGRAM_EYEBROW = "Your cohort program";

/** Primary nav (paths unchanged; labels carry the tone). */
export const PROGRAM_NAV = [
  { to: "/program", label: "Hub" },
  { to: "/program/upload", label: "Your report" },
  { to: "/program/findings", label: "What we found" },
  { to: "/program/select", label: "Your focus" },
  { to: "/program/letters", label: "Letters" },
  { to: "/program/progress", label: "Your path" },
] as const;

export const NAV_SETUP = "Host setup";
export const NAV_GUIDE_DESK = "Guide desk";
export const NAV_ORG_OVERVIEW = "Overview";

/** Human names for backend milestone ids (participant-facing only). */
export function programStageLabel(step: string): string {
  const m: Record<string, string> = {
    enrollment: "Welcomed in",
    upload: "Report shared",
    findings_ready: "Report understood",
    selections_saved: "Focus chosen",
    letters_generated: "Ready to mail",
    paused: "Together on pause",
    complete: "This round complete",
  };
  return m[step] ?? step.replace(/_/g, " ");
}
