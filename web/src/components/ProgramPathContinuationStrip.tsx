import { useLocation } from "react-router-dom";
import {
  isProgramOnboardingNext,
  resolvedProgramNextFromSearch,
} from "@/lib/programEntryContinuation";
import { shouldShowDemoContinuationStrip } from "@/lib/demoProgramBridge";

type Props = {
  stage: "signup" | "login";
};

/**
 * When ?next= points at program onboarding routes, frames auth as part of the program
 * (not a separate “auth app”). Hidden when demo continuation strip is already shown.
 */
export function ProgramPathContinuationStrip({ stage }: Props) {
  const { search } = useLocation();
  if (shouldShowDemoContinuationStrip(search)) return null;

  const nextPath = resolvedProgramNextFromSearch(search);
  if (!isProgramOnboardingNext(nextPath)) return null;

  const step1 = nextPath === "/upload" ? false : true;

  const body =
    stage === "signup"
      ? step1
        ? "You’re entering your real program — not a separate signup flow. After this account step: confirm your email, then Step 1 is get your credit report."
        : "You’re entering your real program. After this account step: confirm your email, then you’ll upload your report — where analysis begins."
      : step1
        ? "You’re signing back into the same program. After you’re in: Step 1 is get your credit report (or the next step your account is ready for)."
        : "You’re signing back into the same program. Next you’ll upload your report — where we parse your file and move you forward.";

  return (
    <div
      className="mt-6 rounded-xl border border-white/[0.12] bg-lab-surface/60 px-4 py-3.5"
      role="status"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-lab-muted">
        Continuing your program
      </p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">{body}</p>
      <p className="mt-2 text-xs text-lab-subtle">
        Next program step after email:{" "}
        <span className="font-medium text-lab-text">
          {step1 ? "Get your credit report" : "Upload your report"}
        </span>
        .
      </p>
    </div>
  );
}
