import { Link } from "react-router-dom";
import { showLaunchHubAuthFooterLink } from "@/lib/launchPreviewAccess";

/** Footer link to `/launch-preview` when dev or preview env is on (see `launchPreviewAccess`). */
export function LaunchHubNavLink() {
  if (!showLaunchHubAuthFooterLink()) return null;
  return (
    <p className="mt-8 text-center text-xs text-lab-subtle">
      <Link
        to="/launch-preview"
        className="text-lab-muted underline decoration-white/10 underline-offset-2 hover:text-lab-accent hover:decoration-lab-accent/40"
      >
        Page hub — status map &amp; live previews (internal)
      </Link>
    </p>
  );
}
