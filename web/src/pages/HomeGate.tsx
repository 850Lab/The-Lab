import { LandingFirstTime } from "@/pages/LandingFirstTime";

/**
 * Home is the signed-out / pre-workflow landing. When a session + workflow exist,
 * `CustomerWorkflowShell` redirects away from `/` before this route renders.
 */
export function HomeGate() {
  return <LandingFirstTime />;
}
