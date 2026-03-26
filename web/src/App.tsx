import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AnalysisPage } from "@/pages/AnalysisPage";
import { ConfirmationPage } from "@/pages/ConfirmationPage";
import { LettersReadyPage } from "@/pages/LettersReadyPage";
import { PaymentPage } from "@/pages/PaymentPage";
import { StrategyPage } from "@/pages/StrategyPage";
import { UploadStep } from "@/pages/UploadStep";
import { HomeGate } from "@/pages/HomeGate";
import { MailingPage } from "@/pages/MailingPage";
import { ProofVerificationPage } from "@/pages/ProofVerificationPage";
import { EscalationActionPage } from "@/pages/EscalationActionPage";
import { EscalationPage } from "@/pages/EscalationPage";
import { TrackingPage } from "@/pages/TrackingPage";
import { MissionControlLayout } from "@/pages/mission-control/MissionControlLayout";
import { McOverview } from "@/pages/mission-control/McOverview";
import { McWorkflows } from "@/pages/mission-control/McWorkflows";
import { McWorkflowDetail } from "@/pages/mission-control/McWorkflowDetail";
import { McExceptions } from "@/pages/mission-control/McExceptions";
import { McResponses } from "@/pages/mission-control/McResponses";
import { McReminders } from "@/pages/mission-control/McReminders";
import { McAudit } from "@/pages/mission-control/McAudit";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/mission-control" element={<MissionControlLayout />}>
          <Route index element={<McOverview />} />
          <Route path="workflows" element={<McWorkflows />} />
          <Route path="workflows/:workflowId" element={<McWorkflowDetail />} />
          <Route path="exceptions" element={<McExceptions />} />
          <Route path="responses" element={<McResponses />} />
          <Route path="reminders" element={<McReminders />} />
          <Route path="audit" element={<McAudit />} />
        </Route>
        <Route path="/" element={<HomeGate />} />
        <Route path="/upload" element={<UploadStep />} />
        <Route path="/analyze" element={<AnalysisPage />} />
        <Route path="/prepare" element={<ConfirmationPage />} />
        <Route path="/strategy" element={<StrategyPage />} />
        <Route path="/payment" element={<PaymentPage />} />
        <Route path="/letters" element={<LettersReadyPage />} />
        <Route path="/proof" element={<ProofVerificationPage />} />
        <Route path="/send" element={<MailingPage />} />
        <Route path="/tracking" element={<TrackingPage />} />
        <Route path="/escalation" element={<EscalationPage />} />
        <Route path="/escalation-action" element={<EscalationActionPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
