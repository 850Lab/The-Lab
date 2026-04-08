import { WAITLIST_MODE } from "@/lib/productGates";
import { LandingFirstTime } from "@/pages/LandingFirstTime";
import { LandingWaitlist } from "@/pages/LandingWaitlist";

/**
 * Home is the signed-out / pre-workflow landing. When a session + workflow exist,
 * `CustomerWorkflowShell` redirects away from `/` before this route renders.
 */
export function HomeGate() {
  return WAITLIST_MODE ? <LandingWaitlist /> : <LandingFirstTime />;
}
