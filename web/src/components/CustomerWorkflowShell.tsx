import { Navigate, Outlet, useLocation } from "react-router-dom";
import { WorkflowIntegrityBanner } from "@/components/WorkflowIntegrityBanner";
import {
  CUSTOMER_WORKFLOW_GUARD_PATHS,
  isEscalationPath,
} from "@/lib/workflowStepRoutes";
import { useAuth } from "@/providers/AuthContext";
import { useCustomerWorkflow } from "@/providers/CustomerWorkflowContext";

const PUBLIC_UNAUTH_PATHS = new Set(["/", "/login", "/signup"]);
const VERIFY_EMAIL_PATH = "/verify-email";

/**
 * Enforces auth + backend-driven customer routes when a session + workflow exist.
 * Does not wrap Mission Control (separate route tree).
 */
export function CustomerWorkflowShell() {
  const loc = useLocation();
  const path = loc.pathname;
  const auth = useAuth();
  const ctx = useCustomerWorkflow();

  if (auth.authBootstrapping) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-2 px-4 text-center text-sm text-white/70">
        <p>Loading…</p>
      </div>
    );
  }

  if (!auth.token) {
    if (!PUBLIC_UNAUTH_PATHS.has(path)) {
      return <Navigate to="/login" replace state={{ from: path }} />;
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
    (path === "/login" || path === "/signup")
  ) {
    if (ctx.workflowId) {
      return <Navigate to={ctx.canonicalCustomerPath} replace />;
    }
    return <Navigate to="/" replace />;
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
    if (path !== "/") {
      return <Navigate to="/" replace />;
    }
    return <Outlet />;
  }

  if (isEscalationPath(path)) {
    return <Outlet />;
  }

  if (
    CUSTOMER_WORKFLOW_GUARD_PATHS.has(path) &&
    path !== ctx.canonicalCustomerPath
  ) {
    return <Navigate to={ctx.canonicalCustomerPath} replace />;
  }

  return (
    <>
      <WorkflowIntegrityBanner />
      <Outlet />
    </>
  );
}
