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
import { McCustomers } from "@/pages/mission-control/McCustomers";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
      <Routes>
        <Route path="/mission-control" element={<MissionControlLayout />}>
          <Route index element={<McOverview />} />
          <Route path="workflows" element={<McWorkflows />} />
          <Route path="workflows/:workflowId" element={<McWorkflowDetail />} />
          <Route path="exceptions" element={<McExceptions />} />
          <Route path="responses" element={<McResponses />} />
          <Route path="reminders" element={<McReminders />} />
          <Route path="audit" element={<McAudit />} />
          <Route path="customers" element={<McCustomers />} />
        </Route>

        <Route
          element={
            <CustomerWorkflowProvider>
              <CustomerWorkflowShell />
            </CustomerWorkflowProvider>
          }
        >
          <Route path="/" element={<HomeGate />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/signup" element={<SignupPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/get-report" element={<ReportAcquisitionPage />} />
          <Route path="/get-report/idiq" element={<ReportAcquisitionIdiqBridgePage />} />
          <Route path="/upload" element={<UploadStep />} />
          <Route path="/analyze" element={<AnalysisPage />} />
          <Route path="/prepare" element={<ConfirmationPage />} />
          <Route path="/strategy" element={<StrategyPage />} />
          <Route path="/payment" element={<PaymentPage />} />
          <Route path="/letters" element={<LettersReadyPage />} />
          <Route path="/proof" element={<ProofVerificationPage />} />
          <Route path="/send" element={<MailingPage />} />
          <Route path="/tracking" element={<TrackingPage />} />
          <Route path="/responses" element={<ResponseIntakePage />} />
          <Route path="/escalation" element={<EscalationPage />} />
          <Route path="/escalation-action" element={<EscalationActionPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
