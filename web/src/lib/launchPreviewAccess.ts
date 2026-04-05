const UNLOCK_KEY = "launch_preview_unlocked_v1";

/**
 * When true, `/launch-preview` shows the full manifest UI (still may require passphrase below).
 * The route stays registered in `App.tsx` so disabled builds show instructions instead of
 * matching `*` and redirecting to `/`.
 */
export function isLaunchPreviewRouteEnabled(): boolean {
  if (import.meta.env.DEV) return true;
  return import.meta.env.VITE_LAUNCH_PREVIEW_ENABLED === "1";
}

/** Optional shared passphrase for staging (set in `web` env). Empty = no extra gate. */
export function launchPreviewPassphraseFromEnv(): string {
  return (import.meta.env.VITE_LAUNCH_PREVIEW_KEY as string | undefined)?.trim() ?? "";
}

export function isLaunchPreviewUnlocked(): boolean {
  if (typeof sessionStorage === "undefined") return false;
  return sessionStorage.getItem(UNLOCK_KEY) === "1";
}

export function setLaunchPreviewUnlocked(ok: boolean): void {
  if (typeof sessionStorage === "undefined") return;
  if (ok) sessionStorage.setItem(UNLOCK_KEY, "1");
  else sessionStorage.removeItem(UNLOCK_KEY);
}

export function launchPreviewNeedsPassphrase(): boolean {
  return launchPreviewPassphraseFromEnv().length > 0;
}

/** Muted footer link on login/signup — dev always; prod when preview or explicit opt-in. */
export function showLaunchHubAuthFooterLink(): boolean {
  if (import.meta.env.DEV) return true;
  if (import.meta.env.VITE_LAUNCH_PREVIEW_ENABLED === "1") return true;
  if (import.meta.env.VITE_SHOW_PAGE_HUB_LINK === "1") return true;
  return false;
}
