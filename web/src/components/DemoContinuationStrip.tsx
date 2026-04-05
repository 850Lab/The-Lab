import { useLocation } from "react-router-dom";
import {
  isDemoContinuationSearch,
  readDemoProgramBridge,
  shouldShowDemoContinuationStrip,
} from "@/lib/demoProgramBridge";

type Props = {
  /** "signup" | "login" — small copy tweaks */
  stage: "signup" | "login";
};

export function DemoContinuationStrip({ stage }: Props) {
  const { search } = useLocation();
  if (!shouldShowDemoContinuationStrip(search)) return null;

  const fromUrl = isDemoContinuationSearch(search);
  const stored = readDemoProgramBridge();
  const fromPreview =
    fromUrl ||
    stored?.source === "demo_run" ||
    stored?.source === "demo_lead" ||
    stored?.source === "demo_welcome";

  const headline = fromPreview
    ? "Continuing from the same program (preview)"
    : "Continuing your program";

  const body =
    stage === "signup"
      ? "Same program you previewed — now on your file. After this account step: confirm your email, then Step 1 is get your credit report (what powers your analysis)."
      : "Sign in to pick up the same program. Next step when you’re in: get your credit report (Step 1), then upload — unless your account is already past that.";

  return (
    <div
      className="mt-6 rounded-xl border border-lab-accent/25 bg-gradient-to-b from-lab-accent/[0.08] to-lab-surface/40 px-4 py-3.5"
      role="status"
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-lab-accent">{headline}</p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">{body}</p>
    </div>
  );
}
