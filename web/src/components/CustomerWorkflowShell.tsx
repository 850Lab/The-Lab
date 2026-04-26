import { useLayoutEffect } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ProgramShellFrame } from "@/components/ProgramShellFrame";
import { OrionCustomerStrip } from "@/components/OrionCustomerStrip";
import { WorkflowIntegrityBanner } from "@/components/WorkflowIntegrityBanner";
import { CUSTOMER_WORKFLOW_GUARD_PATHS, isOrgProgramPath } from "@/lib/workflowStepRoutes";
import {
  publicUnauthPaths,
  signedOutAuthEntryPath,
  WAITLIST_MODE,
} from "@/lib/productGates";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";
const VERIFY_EMAIL_PATH = "/verify-email";

/** Logged-in + verified but no workflow yet: same pre-workflow pages as guests. */
const PRE_WORKFLOW_PATHS = new Set([
  "/",
  "/get-report",
  "/get-report/idiq",
  "/upload",
]);

/**
 * Enforces auth + backend-driven customer routes when a session + workflow exist.
 * Does not wrap Mission Control (separate route tree).
 */
export function CustomerWorkflowShell() {
  const loc = useLocation();
  const path = loc.pathname;
  const auth = useAuth();
  const ctx = useCustomerWorkflow();

  /** React Router does not reset scroll on SPA navigations; long pages (e.g. get-report) left users mid-scroll on the next step. */
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [path]);

  if (auth.authBootstrapping) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2 px-4 text-center text-sm text-white/70">
        <p>Loading your account…</p>
      </div>
    );
  }

  if (!auth.token) {
    if (!publicUnauthPaths().has(path)) {
      return (
        <Navigate
          to={signedOutAuthEntryPath()}
          replace
          state={{ from: path }}
        />
      );
    }
    return <Outlet />;
  }

  if (auth.user && !auth.user.emailVerified) {
    if (path !== VERIFY_EMAIL_PATH) {
      return <Navigate to={VERIFY_EMAIL_PATH} replace />;
    }
    return <Outlet />;
  }

  if (
    auth.token &&
    auth.emailVerified &&
    (path === "/login" ||
      path === "/signup" ||
      (WAITLIST_MODE && path === "/waitlist"))
  ) {
    if (ctx.workflowId) {
      const dest = ctx.programState?.canonicalRoute ?? ctx.canonicalCustomerPath;
      return <Navigate to={dest} replace />;
    }
    return <Navigate to="/" replace />;
  }

  if (auth.token && auth.emailVerified && ctx.loading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2 px-4 text-center text-sm text-white/70">
        <p>Loading your program…</p>
      </div>
    );
  }

  if (ctx.error && auth.token && auth.emailVerified) {
    return (
      <div className="p-6 text-center text-sm text-red-300">
        <p className="font-medium">Could not load workflow</p>
        <p className="mt-2 text-white/60">{ctx.error}</p>
      </div>
    );
  }

  if (!ctx.workflowId) {
    if (!PRE_WORKFLOW_PATHS.has(path) && !isOrgProgramPath(path)) {
      return <Navigate to="/" replace />;
    }
    return <Outlet />;
  }

  if (isOrgProgramPath(path)) {
    return (
      <>
        <WorkflowIntegrityBanner />
        <Outlet />
      </>
    );
  }

  const intakeHubPaths = new Set(["/analyze", "/upload"]);
  const onReviewStep = ctx.programState?.currentStep === "review_claims";
  const allowIntakeHub = Boolean(onReviewStep && intakeHubPaths.has(path));

  const allowList = ctx.programState?.allowedNavRoutes ?? [ctx.canonicalCustomerPath];
  const pathAllowed = allowList.includes(path);

  /** Integrity hints: user may proceed to tracking while authoritative step is still `mail`. */
  const allowTrackingWhileMailBlocked =
    ctx.integrityHints?.mailBlocked === true &&
    path === "/tracking" &&
    (ctx.programState?.canonicalRoute === "/send" || ctx.canonicalCustomerPath === "/send");

  if (
    CUSTOMER_WORKFLOW_GUARD_PATHS.has(path) &&
    !pathAllowed &&
    !allowIntakeHub &&
    !allowTrackingWhileMailBlocked
  ) {
    const dest = ctx.programState?.canonicalRoute ?? ctx.canonicalCustomerPath;
    return <Navigate to={dest} replace />;
  }

  return (
    <>
      <WorkflowIntegrityBanner />
      <OrionCustomerStrip />
      <ProgramShellFrame>
        <Outlet />
      </ProgramShellFrame>
    </>
  );
}
