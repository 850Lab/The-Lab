import { Navigate } from "react-router-dom";
import { getWorkflowState, pathForStep } from "@/lib/workflow";
import { LandingFirstTime } from "@/pages/LandingFirstTime";

export function HomeGate() {
  const state = getWorkflowState();
  if (state) {
    return <Navigate to={pathForStep(state.step)} replace />;
  }
  return <LandingFirstTime />;
}
