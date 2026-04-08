/**
 * Product-facing gates (marketing entry, public shell paths).
 * Add future modes here; keep toggles centralized.
 */

/** When true: public site is waitlist-only — no open guest funnel or auth entry from the shell. */
export const WAITLIST_MODE = true;

const OPEN_PUBLIC_UNAUTH_PATHS = [
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/get-report",
  "/get-report/idiq",
  "/upload",
] as const;

/** Signed-out visitors may only open these paths while waitlist mode is on. */
const WAITLIST_PUBLIC_UNAUTH_PATHS = ["/", "/waitlist", "/forgot-password"] as const;

export function publicUnauthPaths(): Set<string> {
  return new Set(
    WAITLIST_MODE ? WAITLIST_PUBLIC_UNAUTH_PATHS : OPEN_PUBLIC_UNAUTH_PATHS,
  );
}

/** Where the shell sends signed-out users who hit a protected customer path. */
export function signedOutAuthEntryPath(): "/login" | "/waitlist" {
  return WAITLIST_MODE ? "/waitlist" : "/login";
}

/** Forgot-password and similar flows: return to the public auth entry (or waitlist home). */
export function signedOutReturnHref(search: string): string {
  if (WAITLIST_MODE) return "/waitlist";
  return `/login${search}`;
}

/** Stored on waitlist leads in demo_leads.meta.intent (Mission Control / reporting). */
export const WAITLIST_LEAD_INTENT = "waitlist";
