/**
 * Customer SPA — authoritative product UI (paired with `api/workflow_app.py`).
 * Streamlit is legacy reference until `docs/STREAMLIT_RETIREMENT.md` parity is met.
 */
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { CustomerWorkflowShell } from "@/components/CustomerWorkflowShell";
import { CustomerWorkflowProvider } from "@/providers/CustomerWorkflowContext";
import { AuthProvider } from "@/providers/AuthContext";
import { AnalysisPage } from "@/pages/AnalysisPage";
import { ConfirmationPage } from "@/pages/ConfirmationPage";
import { LettersReadyPage } from "@/pages/LettersReadyPage";
import { PaymentPage } from "@/pages/PaymentPage";
import { StrategyPage } from "@/pages/StrategyPage";
import { UploadStep } from "@/pages/UploadStep";
import { HomeGate } from "@/pages/HomeGate";
import { LoginPage } from "@/pages/LoginPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { SignupPage } from "@/pages/SignupPage";
import { VerifyEmailPage } from "@/pages/VerifyEmailPage";
import { MailingPage } from "@/pages/MailingPage";
import { ProofVerificationPage } from "@/pages/ProofVerificationPage";
import { EscalationActionPage } from "@/pages/EscalationActionPage";
import { EscalationPage } from "@/pages/EscalationPage";
import { TrackingPage } from "@/pages/TrackingPage";
import { ResponseIntakePage } from "@/pages/ResponseIntakePage";
import { ReportAcquisitionPage } from "@/pages/ReportAcquisitionPage";
import { ReportAcquisitionIdiqBridgePage } from "@/pages/ReportAcquisitionIdiqBridgePage";
import { MissionControlLayout } from "@/pages/mission-control/MissionControlLayout";
import { McOverview } from "@/pages/mission-control/McOverview";
import { McWorkflows } from "@/pages/mission-control/McWorkflows";
import { McWorkflowDetail } from "@/pages/mission-control/McWorkflowDetail";
import { McExceptions } from "@/pages/mission-control/McExceptions";
import { McResponses } from "@/pages/mission-control/McResponses";
import { McReminders } from "@/pages/mission-control/McReminders";
import { McAudit } from "@/pages/mission-control/McAudit";
import { McDemoLeads } from "@/pages/mission-control/McDemoLeads";
import { McArchitectAccessPage } from "@/pages/mission-control/McArchitectAccessPage";
import { ProgramShell } from "@/components/ProgramShell";
import { ProgramHomePage } from "@/pages/program/ProgramHomePage";
import { ProgramUploadPage } from "@/pages/program/ProgramUploadPage";
import { ProgramFindingsPage } from "@/pages/program/ProgramFindingsPage";
import { ProgramSelectPage } from "@/pages/program/ProgramSelectPage";
import { ProgramLettersPage } from "@/pages/program/ProgramLettersPage";
import { ProgramProgressPage } from "@/pages/program/ProgramProgressPage";
import { OrgDeliveryDashboardPage } from "@/pages/program/OrgDeliveryDashboardPage";
import { ProgramOrgSetupPage } from "@/pages/program/ProgramOrgSetupPage";
import { LaunchPreviewApp } from "@/pages/launch-preview/LaunchPreviewApp";
import { LaunchPreviewDashboard } from "@/pages/launch-preview/LaunchPreviewDashboard";
import { LaunchPreviewInspector } from "@/pages/launch-preview/LaunchPreviewInspector";
import { WAITLIST_MODE } from "@/lib/productGates";
import { LandingWaitlist } from "@/pages/LandingWaitlist";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <Routes>
        {/** Legacy URL: same try-first home, scroll to interactive demo. */}
        <Route
          path="/demo"
          element={
            <Navigate
              to={
                WAITLIST_MODE ? "/waitlist" : { pathname: "/", hash: "live-demo" }
              }
              replace
            />
          }
        />

        {/**
         * GTM preview hub: dashboard + per-page inspector (iframe + connection probes).
         * Gate + feature flag: LaunchPreviewApp + launchPreviewAccess.
         */}
        <Route path="/launch-preview" element={<LaunchPreviewApp />}>
          <Route index element={<LaunchPreviewDashboard />} />
          <Route path="view/:slug" element={<LaunchPreviewInspector />} />
        </Route>

        <Route path="/mission-control" element={<MissionControlLayout />}>
          <Route index element={<McOverview />} />
          <Route path="architect-access" element={<McArchitectAccessPage />} />
          <Route path="workflows" element={<McWorkflows />} />
          <Route path="workflows/:workflowId" element={<McWorkflowDetail />} />
          <Route path="demo-leads" element={<McDemoLeads />} />
          <Route path="exceptions" element={<McExceptions />} />
          <Route path="responses" element={<McResponses />} />
          <Route path="reminders" element={<McReminders />} />
          <Route path="audit" element={<McAudit />} />
        </Route>

        {/**
         * Customer shell must be under `path="/"` with *relative* child paths.
         * A pathless parent layout matched `/mission-control` and `/launch-preview` in RR7,
         * so signed-out users hit `Navigate` → `/login` inside the shell (wrong tree).
         */}
        <Route
          path="/"
          element={
            <CustomerWorkflowProvider>
              <CustomerWorkflowShell />
            </CustomerWorkflowProvider>
          }
        >
          <Route index element={<HomeGate />} />
          <Route
            path="waitlist"
            element={
              WAITLIST_MODE ? (
                <LandingWaitlist />
              ) : (
                <Navigate to="/" replace />
              )
            }
          />
          <Route path="login" element={<LoginPage />} />
          <Route path="forgot-password" element={<ForgotPasswordPage />} />
          <Route path="signup" element={<SignupPage />} />
          <Route path="verify-email" element={<VerifyEmailPage />} />
          <Route path="get-report" element={<ReportAcquisitionPage />} />
          <Route path="get-report/idiq" element={<ReportAcquisitionIdiqBridgePage />} />
          <Route path="upload" element={<UploadStep />} />
          <Route path="analyze" element={<AnalysisPage />} />
          <Route path="prepare" element={<ConfirmationPage />} />
          <Route path="strategy" element={<StrategyPage />} />
          <Route path="payment" element={<PaymentPage />} />
          <Route path="letters" element={<LettersReadyPage />} />
          <Route path="proof" element={<ProofVerificationPage />} />
          <Route path="send" element={<MailingPage />} />
          <Route path="tracking" element={<TrackingPage />} />
          <Route path="responses" element={<ResponseIntakePage />} />
          <Route path="escalation" element={<EscalationPage />} />
          <Route path="escalation-action" element={<EscalationActionPage />} />
          <Route path="program" element={<ProgramShell />}>
            <Route index element={<ProgramHomePage />} />
            <Route path="upload" element={<ProgramUploadPage />} />
            <Route path="findings" element={<ProgramFindingsPage />} />
            <Route path="select" element={<ProgramSelectPage />} />
            <Route path="letters" element={<ProgramLettersPage />} />
            <Route path="progress" element={<ProgramProgressPage />} />
            <Route path="setup" element={<ProgramOrgSetupPage />} />
            <Route path="instructor" element={<OrgDeliveryDashboardPage mode="instructor" />} />
            <Route path="org-insights" element={<OrgDeliveryDashboardPage mode="buyer" />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
