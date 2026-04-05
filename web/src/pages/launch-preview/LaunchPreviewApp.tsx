import { type FormEvent, useState } from "react";
import { Link, Outlet } from "react-router-dom";
import {
  isLaunchPreviewRouteEnabled,
  isLaunchPreviewUnlocked,
  launchPreviewNeedsPassphrase,
  launchPreviewPassphraseFromEnv,
  setLaunchPreviewUnlocked,
} from "@/lib/launchPreviewAccess";

export function LaunchPreviewApp() {
  const [pass, setPass] = useState("");
  const [gateErr, setGateErr] = useState<string | null>(null);

  const featureOn = isLaunchPreviewRouteEnabled();
  const needsGate = launchPreviewNeedsPassphrase();
  const unlocked = !needsGate || isLaunchPreviewUnlocked();

  function onUnlock(e: FormEvent) {
    e.preventDefault();
    setGateErr(null);
    const want = launchPreviewPassphraseFromEnv();
    if (pass.trim() === want) {
      setLaunchPreviewUnlocked(true);
      setPass("");
    } else {
      setGateErr("Passphrase does not match.");
    }
  }

  if (!featureOn) {
    return (
      <div className="min-h-full bg-lab-bg px-4 py-16 text-lab-text">
        <div className="mx-auto max-w-lg rounded-xl border border-white/10 bg-lab-surface p-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-lab-muted">GTM preview</p>
          <h1 className="mt-2 text-xl font-semibold">You’re on the right URL</h1>
          <p className="mt-3 text-sm text-lab-muted">
            This is <code className="text-violet-200">/launch-preview</code>, but the hub UI is off in
            this production build. Use <code className="text-violet-200">npm run dev</code> from{" "}
            <code className="text-violet-200">web/</code>, or set{" "}
            <code className="text-violet-200">VITE_LAUNCH_PREVIEW_ENABLED=1</code> in{" "}
            <code className="text-violet-200">web/.env.local</code> and run{" "}
            <code className="text-violet-200">npm run build</code> again.
          </p>
          <Link to="/" className="mt-6 inline-block text-sm text-lab-accent hover:underline">
            ← Back to app
          </Link>
        </div>
      </div>
    );
  }

  if (!unlocked) {
    return (
      <div className="min-h-full bg-lab-bg px-4 py-16 text-lab-text">
        <div className="mx-auto max-w-md rounded-xl border border-violet-500/30 bg-lab-surface p-6 shadow-lg">
          <p className="text-xs font-semibold uppercase tracking-widest text-violet-300/90">GTM preview</p>
          <h1 className="mt-2 text-xl font-semibold">Enter passphrase</h1>
          <p className="mt-2 text-sm text-lab-muted">
            Optional lock via <code className="text-violet-200">VITE_LAUNCH_PREVIEW_KEY</code>. Leave unset for
            no gate.
          </p>
          <form onSubmit={onUnlock} className="mt-5 space-y-3">
            <input
              type="password"
              autoComplete="off"
              value={pass}
              onChange={(e) => setPass(e.target.value)}
              placeholder="Passphrase"
              className="w-full rounded-lg border border-white/15 bg-lab-bg px-3 py-2 text-sm text-lab-text focus:border-violet-500/50 focus:outline-none"
            />
            {gateErr && <p className="text-sm text-red-300">{gateErr}</p>}
            <button
              type="submit"
              className="w-full rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-500"
            >
              Unlock
            </button>
          </form>
          <Link to="/" className="mt-6 inline-block text-sm text-lab-muted hover:text-lab-accent hover:underline">
            ← Back to app
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-lab-bg text-lab-text">
      <header className="sticky top-0 z-40 border-b border-violet-500/25 bg-lab-surface/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex flex-wrap items-center gap-3">
            <Link
              to="/launch-preview"
              className="text-sm font-semibold text-violet-200 hover:text-violet-100"
            >
              GTM page hub
            </Link>
            <span className="hidden text-lab-subtle sm:inline">|</span>
            <p className="text-xs text-lab-muted">
              Cards = status · Open = live page + connections
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/"
              className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-lab-text hover:bg-white/5"
            >
              App home
            </Link>
            {needsGate && (
              <button
                type="button"
                onClick={() => {
                  setLaunchPreviewUnlocked(false);
                  window.location.reload();
                }}
                className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-lab-muted hover:bg-white/5"
              >
                Lock
              </button>
            )}
          </div>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
